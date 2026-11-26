# Fineract — dev-k8s

GitOps giống `banking-demo` / `npd-shop`. Platform (Vault, Harbor, Jenkins, Argo, OTel) đã có trong `cloud-native-platform` — **không cài lại**.

## Thứ tự bắt buộc (không nhảy cóc)

| Bước | Việc | Script / nơi |
|------|------|----------------|
| **1** | Harbor project `npd-fineract` + robot `k8s-pull` / `ci-push` | `scripts/harbor-setup-project.sh` |
| **2** | Vault seed `secret/fineract/{db,harbor,harbor-pull}` + role `fineract-app` | `scripts/vault-seed-fineract.sh` → `vault-setup-k8s-auth.sh` |
| **3** | K8s `harbor-pull-creds` trong `npd-fineract` | `create-harbor-pull-secret.sh` |
| **4** | Jenkins Multibranch + image trên Harbor (hoặc mirror `openmf/*` tạm) | Jenkins UI + `Jenkinsfile` / library `npd-fineract` |
| **5** | Argo AppProject + app-of-apps | `kubectl apply` argocd manifests |

DB lab: Postgres **trong chart** (`fineractdb`), không share schema banking. Credential seed vào Vault; inject Agent bật sau (`values-vault.yaml`).

## Bước 1–3 (chạy trên `npd-master`)

```bash
cd npd-fineract && git checkout dev-k8s && git pull

# 1) Harbor
export HARBOR_ADMIN_PASS='...'   # admin Harbor
bash scripts/harbor-setup-project.sh
# copy HARBOR_PULL_TOKEN / HARBOR_PUSH_TOKEN từ output

# 2) Vault seed + policy/role
export VAULT_TOKEN=...
export HARBOR_PULL_TOKEN=...
export HARBOR_PUSH_TOKEN=...
export REGISTRY=npd-harbor.co
kubectl exec -i -n vault vault-0 -- env \
  VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$VAULT_TOKEN" \
  HARBOR_PULL_TOKEN="$HARBOR_PULL_TOKEN" HARBOR_PUSH_TOKEN="$HARBOR_PUSH_TOKEN" \
  REGISTRY=npd-harbor.co DEBUG=1 \
  bash -s < scripts/vault-seed-fineract.sh

bash ../cloud-native-platform/phase9-gitops-platform/environments/dev-k8s/scripts/vault-setup-k8s-auth.sh

# 3) Pull secret
VAULT_PATH=secret/fineract/harbor-pull NAMESPACES=npd-fineract \
  bash ../cloud-native-platform/phase9-gitops-platform/environments/dev-k8s/scripts/create-harbor-pull-secret.sh
```

## Bước 4 — Jenkins (sau khi có Dockerfile mirror hoặc job sync image)

- Multibranch: repo `npd-fineract`, branch `dev-k8s`, Script Path `Jenkinsfile`
- Catalog: `jenkins-shared-library` project `npd-fineract`
- Tạm thời vẫn có thể Argo pull `openmf/*` từ Docker Hub (không cần Harbor image) — pull-secret không chặn Hub

## Bước 5 — Argo

```bash
# Đồng bộ password DB từ Vault vào Secret K8s (lab, trước khi bật Vault inject)
DB_PASS=$(kubectl exec -n vault vault-0 -- env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=$VAULT_TOKEN \
  vault kv get -field=password secret/fineract/db)
kubectl -n npd-fineract create secret generic fineract-tenants-db-secret \
  --from-literal=username=postgres \
  --from-literal=password="$DB_PASS" \
  --from-literal=jdbc-url='jdbc:postgresql://fineractdb:5432/fineract_tenants' \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f deploy/dev-k8s/argocd/appproject.yaml
kubectl apply -f deploy/dev-k8s/argocd/app-of-apps.yaml

kubectl -n argocd get app | grep fineract
kubectl -n npd-fineract get pods -w
```

Hosts client: `10.100.1.100  fineract.npd.co mifos.npd.co`  
Login UI lab: `mifos` / `password`.

Chi tiết: [`DEPLOY-PLAN.md`](../../DEPLOY-PLAN.md).
