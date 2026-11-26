# deploy/dev-k8s — Fineract trên npd-k8s

Layout giống `banking-demo/deploy/dev-k8s`.

## Bootstrap Argo CD

```bash
# 1) Secret DB lab (sau này → Vault)
kubectl create namespace npd-fineract --dry-run=client -o yaml | kubectl apply -f -
kubectl -n npd-fineract create secret generic fineract-tenants-db-secret \
  --from-literal=username=postgres \
  --from-literal=password='CHANGE_ME' \
  --from-literal=jdbc-url='jdbc:postgresql://fineractdb:5432/fineract_tenants' \
  --dry-run=client -o yaml | kubectl apply -f -

# 2) Harbor pull secret (copy từ ns khác hoặc ExternalSecret)
# 3) Argo
kubectl apply -f deploy/dev-k8s/argocd/appproject.yaml
kubectl apply -f deploy/dev-k8s/argocd/app-of-apps.yaml
```

Chi tiết platform / Vault / Instana: xem root [`DEPLOY-PLAN.md`](../../DEPLOY-PLAN.md).
