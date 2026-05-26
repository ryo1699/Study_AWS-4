# Study_AWS-4

勉強会2026-4の課題1〜4の実装です。

| フォルダ | 内容 |
| --- | --- |
| `Study_AWS-4_1` | CloudFront + ALB + ECR + ECS + RDS のREST API。CloudWatch Logs/Insights、CPU Alarm、Slack通知を追加 |
| `Study_AWS-4_2` | CloudFront + ALB + EC2 + RDS のREST API。GitHub ActionsからSSMでEC2内を更新 |
| `Study_AWS-4_3` | ローカルk8s上のFastAPI Deployment + PostgreSQL Deployment(replica=1) |
| `Study_AWS-4_4` | CloudFront + ALB + EC2 + Docker + ECR + RDS のREST API。EC2上ではvenvではなくECRイメージをdocker runで起動 |

提供された原本の `openapi.yaml` はリポジトリ直下にも置いています。各課題フォルダにも同じ仕様を置き、実装の起点として参照できるようにしています。

## GitHubにStudy_AWS-4だけpushする手順

GitHubで `Study_AWS-4` リポジトリを作ります。Web UIで作る場合は、GitHub右上の `+` -> `New repository` から次を指定します。

```text
Repository name: Study_AWS-4
Owner: ryo1699
Visibility: private または public
Initialize this repository with README: off
```

ローカルでは必ず `Study_AWS-4` の中で `git init` します。親ディレクトリで実行すると、他の勉強会フォルダやホームディレクトリまでGit管理対象になる可能性があります。

```bash
cd /Users/ryo/Documents/研究室/勉強会_AWS_4/Study_AWS-4
git init
git branch -M main
git remote add origin git@github.com:ryo1699/Study_AWS-4.git
git status --short
git add .
git commit -m "Initial Study_AWS-4 implementation"
git push -u origin main
```

`gh` CLIを使う場合:

```bash
cd /Users/ryo/Documents/研究室/勉強会_AWS_4/Study_AWS-4
git init
git branch -M main
gh repo create ryo1699/Study_AWS-4 --private --source=. --remote=origin
git add .
git commit -m "Initial Study_AWS-4 implementation"
git push -u origin main
```

push前に、秘密情報が入っていないことを確認します。

```bash
git status --short
git ls-files | grep -E 'terraform.tfvars|backend.hcl|tfstate|\\.zip' || true
```

何も出なければ、Terraformのローカル設定やstate、Lambda zipはGit管理されていません。

## 共通の事前準備

AWS課題では以下を使います。

- AWS CLIで `ap-northeast-1` に操作できる認証情報
- Terraform `>= 1.6`
- Docker
- EC2 Key Pair `ryo-key`
- GitHub Actions用OIDC IAM Role
- Slack Incoming Webhook URL

GitHub Actions用OIDC Roleは、学習用なら一度だけ次のように作れます。`ACCOUNT_ID` とリポジトリ名を自分の値に合わせます。

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:ryo1699/Study_AWS-4:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

学習用には `AdministratorAccess` を付けると進めやすいです。本番ではECR、ECS、S3、SSM、iam:PassRoleなど必要権限だけに絞ってください。
