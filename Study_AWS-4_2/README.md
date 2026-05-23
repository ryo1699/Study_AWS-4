# 課題2: CloudFront + ALB + EC2 + RDS のREST API

FastAPIのタスクCRUD APIをEC2上のsystemdサービスとして動かします。CloudFront -> ALB -> EC2 -> RDS PostgreSQL の構成です。

ECSとの違いを体験するため、デプロイはGitHub Actionsから次の流れで行います。

```text
GitHub Actions
  -> APIソースをtar.gz化
  -> S3 deploy artifact bucketへアップロード
  -> SSM Run CommandでEC2へ指示
  -> EC2がS3から取得
  -> /opt/study-aws-4-task2/current を更新
  -> systemd serviceを再起動
```

## ローカル確認

```bash
cd Study_AWS-4_2/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

別ターミナル:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"EC2デプロイ確認","description":"SSMで更新する"}'
curl http://localhost:8000/api/tasks
```

## Terraform

課題1と同じTerraform state bucketを使えます。

```bash
cd Study_AWS-4_2/infra/terraform
cp backend.hcl.example backend.hcl
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` を編集します。

```hcl
bucket_name_suffix = "ryo1699"
db_password = "YOUR_DB_PASSWORD"
allowed_ssh_cidr = "YOUR_GLOBAL_IP/32"
bastion_key_name = "ryo-key"
```

実行します。

```bash
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

作成される主なリソース:

- CloudFront distribution
- public ALB
- private subnet上のAPI EC2
- public subnet上のRDS migration用bastion EC2
- private RDS PostgreSQL
- GitHub Actionsから使うdeploy artifact S3 bucket
- EC2更新用のSSM IAM Role / Instance Profile

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

踏み台で実行します。

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

Terraform outputを確認します。

```bash
terraform output deploy_bucket_name
terraform output app_instance_id
terraform output cloudfront_domain_name
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
| `STUDY_AWS_4_2_DEPLOY_BUCKET` | `terraform output -raw deploy_bucket_name` |
| `STUDY_AWS_4_2_APP_INSTANCE_ID` | `terraform output -raw app_instance_id` |

`main` にpushするか、GitHub Actionsの `Deploy Study AWS 4 Task 2 EC2 API` を手動実行します。

## EC2上のサービス確認

GitHub Actions実行後、SSMで状態を確認できます。

```bash
APP_INSTANCE_ID="$(terraform output -raw app_instance_id)"
aws ssm send-command \
  --instance-ids "$APP_INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["systemctl --no-pager --full status study-aws-4-task2-api","curl -s http://localhost:8000/health"]'
```

コマンドIDを取得して結果を確認します。

```bash
aws ssm list-command-invocations \
  --instance-id "$APP_INSTANCE_ID" \
  --details \
  --max-results 1
```

## API動作確認

CloudFront URLを確認します。

```bash
CLOUDFRONT_DOMAIN="$(terraform output -raw cloudfront_domain_name)"
curl "https://$CLOUDFRONT_DOMAIN/health"
curl -X POST "https://$CLOUDFRONT_DOMAIN/api/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"title":"EC2経由のタスク","description":"CloudFront ALB EC2 RDS"}'
curl "https://$CLOUDFRONT_DOMAIN/api/tasks"
```

期待結果:

- `/health` が `{"status":"ok"}` を返す
- `POST /api/tasks` が `201` を返す
- `GET /api/tasks` に作成したタスクが表示される

ECS版と比べると、EC2版はインスタンスOS、Python環境、systemd、成果物配置を自分で管理する必要があります。これが「ECSのデプロイが楽」と感じるポイントです。
