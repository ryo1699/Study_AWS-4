# 課題4: CloudFront + ALB + EC2 + Docker + ECR + RDS のREST API

課題2のEC2版を、venvではなくDockerコンテナで動かす構成にしたものです。CloudFront -> ALB -> EC2 -> Docker container -> RDS PostgreSQL の流れでタスクCRUD APIを公開します。

デプロイはGitHub Actionsから次の流れで行います。

```text
GitHub Actions
  -> docker build
  -> Amazon ECRへdocker push
  -> SSM Run CommandでEC2へ指示
  -> EC2がECRからdocker pull
  -> docker runで既存コンテナを差し替え
  -> API container 起動
```

課題2との違いは、EC2上にPython venvやアプリケーションソースを直接置かない点です。EC2はDocker実行環境として扱い、アプリ更新はECR上のイメージ差し替えで行います。

## ローカル確認

```bash
cd Study_AWS-4_4/api
docker build -t study-aws-4-4-api:local .
docker run --rm -p 8000:8000 \
  -e ENABLE_DEBUG_ERROR_ENDPOINT=true \
  study-aws-4-4-api:local
```

別ターミナル:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"EC2 Docker確認","description":"ECRからpullしてdocker runする"}'
curl http://localhost:8000/api/tasks
curl -i http://localhost:8000/api/debug/error
```

## Terraform

課題1と同じTerraform state bucketを使えます。

```bash
cd Study_AWS-4_4/infra/terraform
cp backend.hcl.example backend.hcl
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` を編集します。

```hcl
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
- APIイメージ格納用ECR repository
- EC2更新用のSSM IAM Role / Instance Profile
- EC2からECR pullするためのIAM権限

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
terraform output ecr_repository_name
terraform output ecr_repository_url
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
| `STUDY_AWS_4_4_ECR_REPOSITORY` | `terraform output -raw ecr_repository_name` |
| `STUDY_AWS_4_4_APP_INSTANCE_ID` | `terraform output -raw app_instance_id` |

`main` にpushするか、GitHub Actionsの `Deploy Study AWS 4 Task 4 EC2 Docker API` を手動実行します。

## EC2上のDocker確認

GitHub Actions実行後、SSMでコンテナ状態を確認できます。

```bash
APP_INSTANCE_ID="$(terraform output -raw app_instance_id)"
aws ssm send-command \
  --instance-ids "$APP_INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker ps","sudo docker logs --tail 100 study-aws-4-task4-api","curl -s http://localhost:8000/health"]'
```

コマンドIDを取得して結果を確認します。

```bash
aws ssm list-command-invocations \
  --instance-id "$APP_INSTANCE_ID" \
  --details \
  --max-results 1
```

期待結果:

- `study-aws-4-task4-api` コンテナが `Up` になっている
- `/health` が `{"status":"ok"}` を返す
- EC2上のアプリ起動はvenvではなく `docker run` で行われている

## API動作確認

CloudFront URLを確認します。

```bash
CLOUDFRONT_DOMAIN="$(terraform output -raw cloudfront_domain_name)"
curl "https://$CLOUDFRONT_DOMAIN/health"
curl -X POST "https://$CLOUDFRONT_DOMAIN/api/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"title":"EC2 Docker経由のタスク","description":"CloudFront ALB EC2 Docker RDS"}'
curl "https://$CLOUDFRONT_DOMAIN/api/tasks"
```

期待結果:

- `/health` が `{"status":"ok"}` を返す
- `POST /api/tasks` が `201` を返す
- `GET /api/tasks` に作成したタスクが表示される

## 手動でDocker差し替えする場合

GitHub Actionsを使わずにEC2側の差し替えだけ試す場合は、ECRへpush済みのイメージURIを指定します。

```bash
IMAGE_URI="$(terraform output -raw ecr_repository_url):latest"
APP_INSTANCE_ID="$(terraform output -raw app_instance_id)"

aws ssm send-command \
  --instance-ids "$APP_INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters "commands=[\"sudo /opt/study-aws-4-task4/deploy.sh $IMAGE_URI\",\"sudo docker ps\"]"
```
