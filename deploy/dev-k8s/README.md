# Fineract — dev-k8s

GitOps giống `banking-demo` / `npd-shop`. **Postgres = `postgres-ha` platform** (Job tạo user/DB `fineract` + `fineract_tenants` / `fineract_default`) — không deploy Postgres trong chart.

## Thứ tự bắt buộc

| Bước | Việc | Script / nơi |
|------|------|----------------|
| **1** | Harbor project `npd-fineract` + robot | `scripts/harbor-setup-project.sh` |
| **2** | Vault seed + role `fineract-app` / `fineract-db-init` | `vault-seed-fineract.sh` → `vault-setup-k8s-auth.sh` |
| **3** | `harbor-pull-creds` | `create-harbor-pull-secret.sh` |
| **4** | Jenkins CI + Harbor images | Multibranch + mirror Dockerfiles |
| **5** | Argo: `fineract-db-init` → `fineract-app` | `argocd/*` |

## Bước 4 — Jenkins CI/CD (build từ source)

| Service | Khi sửa gì thì build | Cách build |
|---------|----------------------|------------|
| `fineract-server` | `fineract-provider/`, `fineract-core/`, … | Gradle + **DinD** (QueryDSL Testcontainers) → Kaniko đóng JAR (20–60 phút) |
| `web-app` | `docker/web-app/` | Kaniko mirror `openmf/web-app` |

**Lưu ý:** Không build Gradle *trong* Kaniko. Pod CI dùng sidecar `docker:27-dind` (privileged). Cluster phải cho phép privileged containers.

```bash
# Force: BUILD_TARGET=fineract-server
# Log OK: "DinD ready" → bootJar → Kaniko push
```

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

Hosts client: `10.100.1.100  npd-fineract.co npd-mifos.co`  
UI: https://npd-mifos.co — login lab `mifos` / `password`  
API: https://npd-fineract.co/fineract-provider/...

### f5-lb (NGINX Plus)

```bash
# Từ máy có repo cloud-native-platform
scp phase9-gitops-platform/environments/dev-k8s/f5-lb/conf.d/63-npd-fineract.conf \
    phase9-gitops-platform/environments/dev-k8s/f5-lb/conf.d/64-npd-mifos.conf \
    sysadmin@10.100.1.100:/tmp/
ssh sysadmin@10.100.1.100 'sudo cp /tmp/63-npd-fineract.conf /tmp/64-npd-mifos.conf /etc/nginx/conf.d/ && sudo nginx -t && sudo nginx -s reload'
```

Cert `/etc/nginx/certs/tls.crt` cần SAN (hoặc wildcard `*.npd.co` / `npd-*.co`) gồm `npd-fineract.co` + `npd-mifos.co`.
