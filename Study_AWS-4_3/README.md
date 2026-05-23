# 課題3: ローカルk8sでREST API + DBを動かす

ローカルKubernetes上でFastAPIのREST APIとPostgreSQLを動かします。

構成:

```text
kubectl port-forward
  -> Service task-api
  -> Deployment task-api replicas=2
  -> Service postgres
  -> Deployment postgres replicas=1
```

DBは課題条件に合わせてDeploymentのreplicaを1にしています。ローカル練習用なのでPostgreSQLのデータ領域は `emptyDir` です。Podが作り直されるとデータは消えます。

## 前提

どちらかのローカルk8sを用意してください。

- Docker Desktop Kubernetes
- kind
- minikube

以下は `kind` の例です。

```bash
kind create cluster --name study-aws-4-3
```

## APIイメージをビルド

```bash
cd Study_AWS-4_3/api
docker build -t study-aws-4-3-api:local .
```

kindを使う場合は、Dockerイメージをクラスタへ読み込みます。

```bash
kind load docker-image study-aws-4-3-api:local --name study-aws-4-3
```

Docker Desktop Kubernetesの場合は、同じDocker daemonを使うため `kind load` は不要です。

## k8sへデプロイ

```bash
cd Study_AWS-4_3
kubectl apply -k k8s
```

Podの状態を確認します。

```bash
kubectl get pods -n study-aws-4-3 -w
```

期待結果:

```text
postgres-...   1/1   Running
task-api-...   1/1   Running
task-api-...   1/1   Running
```

Deployment条件を確認します。

```bash
kubectl get deploy -n study-aws-4-3
```

期待結果:

```text
NAME       READY   UP-TO-DATE   AVAILABLE
postgres   1/1     1            1
task-api   2/2     2            2
```

## API動作確認

Serviceをローカルに転送します。

```bash
kubectl port-forward -n study-aws-4-3 service/task-api 8000:8000
```

別ターミナルで確認します。

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"k8sで作成","description":"API DeploymentからPostgreSQLへ保存"}'
curl http://localhost:8000/api/tasks
curl -X PUT http://localhost:8000/api/tasks/1 \
  -H 'Content-Type: application/json' \
  -d '{"title":"k8sで更新","description":"Deployment確認","status":"in_progress"}'
curl http://localhost:8000/api/tasks/1
curl -X DELETE http://localhost:8000/api/tasks/1
```

期待結果:

- `/health` が `{"status":"ok"}` を返す
- タスク作成、一覧、更新、削除ができる
- DB Podを消すと `emptyDir` のためデータが消える

## ログ確認

API Pod名を確認します。

```bash
kubectl get pods -n study-aws-4-3 -l app=task-api
```

ログを確認します。

```bash
kubectl logs -n study-aws-4-3 deploy/task-api
```

意図的に500エラーを出す場合:

```bash
curl -i http://localhost:8000/api/debug/error
kubectl logs -n study-aws-4-3 deploy/task-api | grep ERROR
```

## スケール確認

APIだけreplica数を変えられます。

```bash
kubectl scale deployment task-api -n study-aws-4-3 --replicas=3
kubectl get pods -n study-aws-4-3 -l app=task-api
```

DBは状態を持つため、今回の課題ではreplica 1のまま扱います。

## 削除

```bash
kubectl delete namespace study-aws-4-3
```

kindクラスタごと消す場合:

```bash
kind delete cluster --name study-aws-4-3
```
