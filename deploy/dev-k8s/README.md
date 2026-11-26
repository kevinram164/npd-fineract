# Fineract — dev-k8s

GitOps giống `banking-demo` / `npd-shop`. **Postgres = `postgres-ha` platform** (Job tạo user/DB `fineract` + `fineract_tenants` / `fineract_default`) — không deploy Postgres trong chart.

## Thứ tự bắt buộc

| Bước | Việc | Script / nơi |
|------|------|----------------|
| **1** | Harbor project `npd-fineract` + robot | `scripts/harbor-setup-project.sh` |
| **2** | Vault seed + role `fineract-app` / `fineract-db-init` | `vault-seed-fineract.sh` → `vault-setup-k8s-auth.sh` |
| **3** | `harbor-pull-creds` | `create-harbor-pull-secret.sh` |
| **4** | Jenkins / mirror image (tuỳ) | Multibranch + library |
| **5** | Argo: `fineract-db-init` → `fineract-app` | `argocd/*` |

## Bước 1–3

```bash
cd npd-fineract && git checkout dev-k8s && git pull
export HARBOR_ADMIN_PASS=...
bash scripts/harbor-setup-project.sh

export VAULT_TOKEN=... HARBOR_PULL_TOKEN=... HARBOR_PUSH_TOKEN=... REGISTRY=npd-harbor.co
kubectl exec -i -n vault vault-0 -- env \
  VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$VAULT_TOKEN" \
  HARBOR_PULL_TOKEN="$HARBOR_PULL_TOKEN" HARBOR_PUSH_TOKEN="$HARBOR_PUSH_TOKEN" \
  REGISTRY=npd-harbor.co DEBUG=1 \
  bash -s < scripts/vault-seed-fineract.sh

bash ../cloud-native-platform/phase9-gitops-platform/environments/dev-k8s/scripts/vault-setup-k8s-auth.sh

VAULT_PATH=secret/fineract/harbor-pull NAMESPACES=npd-fineract \
  bash ../cloud-native-platform/phase9-gitops-platform/environments/dev-k8s/scripts/create-harbor-pull-secret.sh
```

## Bước 5 — Argo

```bash
VAULT_TOKEN=... bash scripts/bootstrap-npd-k8s.sh
# hoặc:
kubectl apply -f deploy/dev-k8s/argocd/appproject.yaml
kubectl apply -f deploy/dev-k8s/argocd/app-of-apps.yaml
```

Hosts: `10.100.1.100  fineract.npd.co mifos.npd.co` — login UI lab `mifos` / `password`.
