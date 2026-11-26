#!/usr/bin/env bash
# Chạy trên npd-master (có kubectl + quyền cluster).
# Phase 1: secret DB + Argo AppProject + app-of-apps.
set -euo pipefail

NS=npd-fineract
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB_PASS="${FINERACT_DB_PASSWORD:-$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)}"

echo "==> Namespace $NS"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -

echo "==> Secret fineract-tenants-db-secret"
kubectl -n "$NS" create secret generic fineract-tenants-db-secret \
  --from-literal=username=postgres \
  --from-literal=password="$DB_PASS" \
  --from-literal=jdbc-url='jdbc:postgresql://fineractdb:5432/fineract_tenants' \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Argo AppProject + root app"
kubectl apply -f "$ROOT/deploy/dev-k8s/argocd/appproject.yaml"
kubectl apply -f "$ROOT/deploy/dev-k8s/argocd/app-of-apps.yaml"

echo
echo "Done. Theo dõi:"
echo "  kubectl -n argocd get app fineract-root-dev-k8s fineract-app"
echo "  kubectl -n $NS get pods -w"
echo
echo "DB password (lưu Vault sau): đã set trong secret (không in ra trừ khi DEBUG=1)"
if [[ "${DEBUG:-0}" == "1" ]]; then
  echo "  password=$DB_PASS"
fi
echo
echo "Hosts (nếu chưa có DNS): thêm fineract.npd.co / mifos.npd.co → ingress IP"
echo "Login UI lab: mifos / password  (khi web-app sẵn)"
