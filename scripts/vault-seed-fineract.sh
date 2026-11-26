#!/usr/bin/env bash
# Seed Vault cho npd-fineract (lab). Chạy trong vault-0 hoặc bastion có vault CLI.
#
# Trước đó: scripts/harbor-setup-project.sh → HARBOR_PULL_TOKEN / HARBOR_PUSH_TOKEN
#
#   export VAULT_ADDR=http://127.0.0.1:8200
#   export VAULT_TOKEN=...
#   export HARBOR_PULL_TOKEN='...'
#   export HARBOR_PUSH_TOKEN='...'
#   export REGISTRY=npd-harbor.co
#   bash scripts/vault-seed-fineract.sh
#
# Từ máy có kubectl:
#   kubectl exec -i -n vault vault-0 -- env \
#     VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=$VAULT_TOKEN \
#     HARBOR_PULL_TOKEN=... HARBOR_PUSH_TOKEN=... REGISTRY=npd-harbor.co \
#     bash -s < scripts/vault-seed-fineract.sh
set -euo pipefail

: "${VAULT_ADDR:?set VAULT_ADDR}"
: "${VAULT_TOKEN:?set VAULT_TOKEN}"
: "${HARBOR_PULL_TOKEN:?set HARBOR_PULL_TOKEN (robot npd-fineract+k8s-pull)}"
: "${HARBOR_PUSH_TOKEN:?set HARBOR_PUSH_TOKEN (robot npd-fineract+ci-push)}"

REGISTRY="${REGISTRY:-npd-harbor.co}"
# Lab: Postgres trong ns npd-fineract (Service fineractdb). Phase sau có thể trỏ shared PG.
PG_HOST="${PG_HOST:-fineractdb.npd-fineract.svc.cluster.local}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${FINERACT_DB_PASSWORD:-$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)}"
JDBC_URL="${JDBC_URL:-jdbc:postgresql://${PG_HOST}:5432/fineract_tenants}"

echo "==> secret/fineract/db"
vault kv put secret/fineract/db \
  username="${DB_USER}" \
  password="${DB_PASSWORD}" \
  jdbc-url="${JDBC_URL}" \
  FINERACT_HIKARI_USERNAME="${DB_USER}" \
  FINERACT_HIKARI_PASSWORD="${DB_PASSWORD}" \
  FINERACT_HIKARI_JDBC_URL="${JDBC_URL}" \
  FINERACT_DEFAULT_TENANTDB_UID="${DB_USER}" \
  FINERACT_DEFAULT_TENANTDB_PWD="${DB_PASSWORD}"

echo "==> secret/fineract/harbor-pull"
vault kv put secret/fineract/harbor-pull \
  registry="${REGISTRY}" \
  username='robot$npd-fineract+k8s-pull' \
  password="${HARBOR_PULL_TOKEN}"

echo "==> secret/fineract/harbor (Jenkins Kaniko)"
vault kv put secret/fineract/harbor \
  username='robot$npd-fineract+ci-push' \
  password="${HARBOR_PUSH_TOKEN}"

echo "==> done"
echo "  vault kv get secret/fineract/db"
echo "  vault kv get secret/fineract/harbor-pull"
echo "  vault kv get secret/fineract/harbor"
echo
echo "Tiếp:"
echo "  1) bash cloud-native-platform/.../vault-setup-k8s-auth.sh   # role fineract-app"
echo "  2) VAULT_PATH=secret/fineract/harbor-pull NAMESPACES=npd-fineract \\"
echo "       bash .../create-harbor-pull-secret.sh"
if [[ "${DEBUG:-0}" == "1" ]]; then
  echo "  DB password=${DB_PASSWORD}"
fi
