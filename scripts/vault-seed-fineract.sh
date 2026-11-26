#!/bin/sh
# Seed Vault cho npd-fineract. Chạy trong vault-0 (chỉ có sh, không bash/openssl).
#
# Trên npd-master:
#   export VAULT_TOKEN=...
#   export HARBOR_PULL_TOKEN=...
#   export HARBOR_PUSH_TOKEN=...
#   export REGISTRY=npd-harbor.co
#   export FINERACT_DB_PASSWORD="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
#   kubectl exec -i -n vault vault-0 -- env \
#     VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$VAULT_TOKEN" \
#     HARBOR_PULL_TOKEN="$HARBOR_PULL_TOKEN" HARBOR_PUSH_TOKEN="$HARBOR_PUSH_TOKEN" \
#     REGISTRY=npd-harbor.co FINERACT_DB_PASSWORD="$FINERACT_DB_PASSWORD" DEBUG=1 \
#     sh -s < scripts/vault-seed-fineract.sh
set -eu

: "${VAULT_ADDR:?set VAULT_ADDR}"
: "${VAULT_TOKEN:?set VAULT_TOKEN}"
: "${HARBOR_PULL_TOKEN:?set HARBOR_PULL_TOKEN}"
: "${HARBOR_PUSH_TOKEN:?set HARBOR_PUSH_TOKEN}"
: "${FINERACT_DB_PASSWORD:?set FINERACT_DB_PASSWORD on host before piping into vault-0}"

REGISTRY="${REGISTRY:-npd-harbor.co}"
PG_HOST="${PG_HOST:-postgres-ha-postgresql-primary.postgres.svc.cluster.local}"
DB_USER="${DB_USER:-fineract}"
DB_PASSWORD="${FINERACT_DB_PASSWORD}"
JDBC_URL="${JDBC_URL:-jdbc:postgresql://${PG_HOST}:5432/fineract_tenants}"

echo "==> secret/fineract/db (user fineract on postgres-ha)"
vault kv put secret/fineract/db \
  username="${DB_USER}" \
  password="${DB_PASSWORD}" \
  database=fineract_tenants \
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
if [ "${DEBUG:-0}" = "1" ]; then
  echo "  DB password=${DB_PASSWORD}"
fi
