# deploy/dev-k8s — Fineract trên npd-k8s

## Phase 1 — Bootstrap (chạy trên `npd-master`)

```bash
# Clone / pull repo
git clone https://github.com/kevinram164/npd-fineract.git
cd npd-fineract
git checkout dev-k8s

chmod +x scripts/bootstrap-npd-k8s.sh
DEBUG=1 ./scripts/bootstrap-npd-k8s.sh   # in password DB lần đầu

# Theo dõi Argo + pods
kubectl -n argocd get app | grep fineract
kubectl -n npd-fineract get pods -w
```

Image Phase 1: `openmf/fineract:develop` + `openmf/web-app:dev` (Docker Hub, chưa cần Harbor).

### Kiểm tra

```bash
kubectl -n npd-fineract get ingress,svc,pods
# API (port-forward nếu chưa DNS)
kubectl -n npd-fineract port-forward svc/fineract-server 8080:8080
curl -sk http://127.0.0.1:8080/fineract-provider/actuator/health
```

Login UI lab (khi web Ready): user `mifos` / password `password`.

Chi tiết đầy đủ: [`DEPLOY-PLAN.md`](../../DEPLOY-PLAN.md).
