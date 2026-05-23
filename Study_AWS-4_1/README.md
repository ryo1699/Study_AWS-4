# 課題1: CloudFront + ALB + ECR + ECS + RDS + CloudWatch Logs/Alarm

第2回の `Study_AWS-2_1` を土台にしたREST APIです。FastAPIをECS Fargateで動かし、CloudFront -> ALB -> ECS -> RDS PostgreSQL の流れでタスクCRUD APIを公開します。

今回の追加点は次です。

- APIログをJSON形式でstdoutへ出し、ECSのawslogs driverでCloudWatch Logsへ集約する
- `ERROR` ログだけをCloudWatch Logs Insightsで取り出せるようにする
- ECS ServiceのCPU使用率が5%を超えたらCloudWatch Alarm -> SNS -> Lambda -> Slackへ通知する
- GitHub Actionsで `docker build -> ECR push -> ECS task definition更新 -> ECS service deploy` を行う

## エラー設計

このAPIでは、エラーを次の2種類に分けています。

| 種別 | HTTP | ログレベル | 例 | 理由 |
| --- | --- | --- | --- | --- |
| 利用者や入力に起因する想定内エラー | 4xx | `WARNING` | 存在しないタスクID | APIとして正常に扱える失敗なので、運用アラート対象にしない |
| サーバ内部の想定外エラー | 5xx | `ERROR` | DB接続失敗、未処理例外 | 運用者が調査すべき失敗なので、CloudWatch Logs Insightsで抽出対象にする |

エラーレスポンスには `message`、`errorCode`、`requestId` を返します。ログにも同じ `requestId` を出すため、利用者から問い合わせが来たときに該当ログを追いやすくしています。

## ローカル確認

```bash
cd Study_AWS-4_1/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
ENABLE_DEBUG_ERROR_ENDPOINT=true python -m uvicorn app.main:app --reload
```

別ターミナルで確認します。

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"ログ確認","description":"CloudWatchで追う","status":"pending"}'
curl http://localhost:8000/api/tasks
curl http://localhost:8000/api/tasks/999
curl -i http://localhost:8000/api/debug/error
```

期待する結果:

- `/health` は `{"status":"ok"}` を返す
- タスク作成は `201` を返す
- 存在しないIDは `404` と `TASK_NOT_FOUND` を返し、ログは `WARNING`
- `/api/debug/error` は意図的に `500` を返し、ログは `ERROR`

## Terraform

Terraform state用S3バケットを初回だけ作成します。

```bash
aws s3api create-bucket \
  --bucket study-aws-4-terraform-state-ryo1699 \
  --region ap-northeast-1 \
  --create-bucket-configuration LocationConstraint=ap-northeast-1

aws s3api put-bucket-versioning \
  --bucket study-aws-4-terraform-state-ryo1699 \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket study-aws-4-terraform-state-ryo1699 \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

設定ファイルを作ります。

```bash
cd Study_AWS-4_1/infra/terraform
cp backend.hcl.example backend.hcl
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` を編集します。

```hcl
db_password = "YOUR_DB_PASSWORD"
allowed_ssh_cidr = "YOUR_GLOBAL_IP/32"
bastion_key_name = "ryo-key"
slack_webhook_url = "https://hooks.slack.com/services/XXX/YYY/ZZZ"
cpu_alarm_threshold = 5
enable_debug_error_endpoint = true
```

実行します。

```bash
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

## RDS migration

Terraform outputを確認します。

```bash
BASTION_PUBLIC_IP="$(terraform output -raw bastion_public_ip)"
RDS_ENDPOINT="$(terraform output -raw rds_endpoint)"
echo "$BASTION_PUBLIC_IP"
echo "$RDS_ENDPOINT"
```

SQLを踏み台へコピーします。

```bash
scp -i /Users/ryo/Documents/研究室/勉強会_AWS_4/AWS_resources/ryo-key.pem \
  ../../api/migrations/001_create_tasks.sql \
  ec2-user@"$BASTION_PUBLIC_IP":/home/ec2-user/001_create_tasks.sql
```

踏み台に入ってmigrationします。

```bash
ssh -i /Users/ryo/Documents/研究室/勉強会_AWS_4/AWS_resources/ryo-key.pem \
  ec2-user@"$BASTION_PUBLIC_IP"

sudo dnf install -y postgresql15
export RDS_ENDPOINT="RDS_ENDPOINT_FROM_TERRAFORM_OUTPUT"
export PGPASSWORD="YOUR_DB_PASSWORD"
psql "host=$RDS_ENDPOINT port=5432 dbname=tasks user=app_user sslmode=require" \
  -f /home/ec2-user/001_create_tasks.sql
```

## GitHub Actions CD

Terraform apply後に値を確認します。

```bash
terraform output ecr_repository_url
terraform output ecs_cluster_name
terraform output ecs_service_name
```

GitHub repositoryの `Settings > Secrets and variables > Actions` に設定します。

Secrets:

| Name | Value |
| --- | --- |
| `AWS_ROLE_TO_ASSUME` | GitHub Actions OIDC用IAM Role ARN |

Variables:

| Name | Value |
| --- | --- |
| `AWS_REGION` | `ap-northeast-1` |
| `STUDY_AWS_4_1_ECR_REPOSITORY` | ECR repository名。URLではなく名前 |
| `STUDY_AWS_4_1_ECS_CLUSTER` | `terraform output -raw ecs_cluster_name` |
| `STUDY_AWS_4_1_ECS_SERVICE` | `terraform output -raw ecs_service_name` |
| `STUDY_AWS_4_1_ECS_TASK_DEFINITION` | task definition family名。通常は `study-aws-4-1-api` |

`main` にpushするか、GitHub Actionsの `Deploy Study AWS 4 Task 1 ECS API` を手動実行します。

## CloudWatch Logs確認

CloudFront URLを確認します。

```bash
terraform output cloudfront_domain_name
```

エラーを発生させます。

```bash
CLOUDFRONT_DOMAIN="$(terraform output -raw cloudfront_domain_name)"
curl -i "https://$CLOUDFRONT_DOMAIN/api/debug/error"
```

CloudWatch Logs Insightsで、log group `/ecs/study-aws-4-1-api` を選び、次を実行します。

```sql
fields @timestamp, level, message, errorCode, requestId, path, statusCode
| filter level = "ERROR"
| sort @timestamp desc
| limit 20
```

想定結果:

- `/api/debug/error` の `internal_server_error` または `request_unhandled_exception` が表示される
- `requestId` がレスポンスヘッダー `x-request-id` と一致する

## CPUアラームとSlack通知確認

アラーム名を確認します。

```bash
terraform output cpu_alarm_name
```

手動でSlack通知までの経路を確認する場合:

```bash
aws cloudwatch set-alarm-state \
  --alarm-name "$(terraform output -raw cpu_alarm_name)" \
  --state-value ALARM \
  --state-reason "manual alarm test"
```

期待結果:

- Slackに `Study_AWS-4 課題1: ... is ALARM` の通知が届く

実CPUで確認したい場合は、`cpu_alarm_threshold` をさらに下げて `terraform apply` し、APIへ連続アクセスします。

```bash
for i in $(seq 1 200); do
  curl -s "https://$CLOUDFRONT_DOMAIN/health" >/dev/null &
done
wait
```

確認後、必要なら `enable_debug_error_endpoint = false` にして `terraform apply` してください。
