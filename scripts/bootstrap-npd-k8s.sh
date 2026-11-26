#!/usr/bin/env bash
# Orchestrator lab — KHÔNG thay Bước 1–3. Chỉ apply Secret DB + Argo (Bước 5).
# Chạy sau khi Harbor + Vault seed + harbor-pull-creds đã xong.
#
#   export VAULT_TOKEN=...   # optional: lấy password từ secret/fineract/db
#   bash scripts/bootstrap-npd-k8s.sh
set -euo pipefail

NS=npd-fineract
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VAULT_NS="${VAULT_NS:-vault}"

echo "==> Preflight (Bước 1–3 phải xong trước Argo)"
missing=0
kubectl get ns "$NS" >/dev/null 2>&1 || {
  echo "WARN: ns $NS chưa có — create-harbor-pull-secret.sh sẽ tạo khi chạy Bước 3"
}
if ! kubectl -n "$NS" get secret harbor-pull-creds >/dev/null 2>&1; then
  echo "MISSING: $NS/harbor-pull-creds  → chạy Bước 3 (create-harbor-pull-secret.sh)"
  missing=1
fi
if [[ -n "${VAULT_TOKEN:-}" ]]; then
  if ! kubectl exec -n "${VAULT_NS}" vault-0 -- env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="${VAULT_TOKEN}" \
      vault kv get secret/fineract/db >/dev/null 2>&1; then
    echo "MISSING: secret/fineract/db  → chạy Bước 2 (vault-seed-fineract.sh)"
    missing=1
  fi
else
  echo "NOTE: chưa set VAULT_TOKEN — bỏ qua check Vault; dùng FINERACT_DB_PASSWORD hoặc random"
fi
if [[ "${missing}" -eq 1 && "${FORCE:-0}" != "1" ]]; then
  echo
  echo "Dừng. Hoàn tất Bước 1–3 (xem deploy/dev-k8s/README.md) rồi chạy lại,"
  echo "hoặc FORCE=1 $0 để apply Argo dù thiếu pull-secret (chỉ lab Docker Hub)."
  exit 1
fi

if [[ -n "${VAULT_TOKEN:-}" ]] && kubectl exec -n "${VAULT_NS}" vault-0 -- env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="${VAULT_TOKEN}" \
    vault kv get secret/fineract/db >/dev/null 2>&1; then
  DB_USER="$(kubectl exec -n "${VAULT_NS}" vault-0 -- env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="${VAULT_TOKEN}" \
    vault kv get -field=username secret/fineract/db)"
  DB_PASS="$(kubectl exec -n "${VAULT_NS}" vault-0 -- env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="${VAULT_TOKEN}" \
    vault kv get -field=password secret/fineract/db)"
else
  DB_USER=postgres
  DB_PASS="${FINERACT_DB_PASSWORD:-$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)}"
fi

echo "==> Namespace $NS"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -

echo "==> Secret fineract-tenants-db-secret"
kubectl -n "$NS" create secret generic fineract-tenants-db-secret \
  --from-literal=username="$DB_USER" \
  --from-literal=password="$DB_PASS" \
  --from-literal=jdbc-url='jdbc:postgresql://fineractdb:5432/fineract_tenants' \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> Argo AppProject + root app (Bước 5)"
kubectl apply -f "$ROOT/deploy/dev-k8s/argocd/appproject.yaml"
kubectl apply -f "$ROOT/deploy/dev-k8s/argocd/app-of-apps.yaml"

echo
echo "Done. Theo dõi:"
echo "  kubectl -n argocd get app | grep fineract"
echo "  kubectl -n $NS get pods -w"
if [[ "${DEBUG:-0}" == "1" ]]; then
  echo "  DB password=$DB_PASS"
fi
