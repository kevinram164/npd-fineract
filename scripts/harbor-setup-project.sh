#!/usr/bin/env bash
# Bước 1 — Tạo Harbor project npd-fineract + robot k8s-pull / ci-push.
# Chạy trên máy có curl tới https://npd-harbor.co (npd-master hoặc bastion).
#
#   export HARBOR_ADMIN_USER=admin
#   export HARBOR_ADMIN_PASS='...'   # hoặc lấy từ Vault secret/platform/harbor nếu có
#   bash scripts/harbor-setup-project.sh
#
# Output: HARBOR_PULL_TOKEN / HARBOR_PUSH_TOKEN → đưa vào vault-seed-fineract.sh
set -euo pipefail

HARBOR_URL="${HARBOR_URL:-https://npd-harbor.co}"
HARBOR_ADMIN_USER="${HARBOR_ADMIN_USER:-admin}"
: "${HARBOR_ADMIN_PASS:?export HARBOR_ADMIN_PASS}"
PROJECT="${HARBOR_PROJECT:-npd-fineract}"
CURL=(curl -sk -u "${HARBOR_ADMIN_USER}:${HARBOR_ADMIN_PASS}")

echo "==> Harbor ${HARBOR_URL} project=${PROJECT}"

code="$("${CURL[@]}" -o /dev/null -w '%{http_code}' \
  -X POST "${HARBOR_URL}/api/v2.0/projects" \
  -H 'Content-Type: application/json' \
  -d "{\"project_name\":\"${PROJECT}\",\"public\":false,\"metadata\":{\"public\":\"false\"}}")" || true
case "${code}" in
  201) echo "    project created" ;;
  409) echo "    project already exists" ;;
  *) echo "ERROR create project HTTP ${code}"; exit 1 ;;
esac

create_robot() {
  local short_name="$1"   # k8s-pull | ci-push
  local push="$2"         # true|false
  local access
  if [[ "${push}" == "true" ]]; then
    access='[{"resource":"repository","action":"pull"},{"resource":"repository","action":"push"},{"resource":"artifact","action":"read"},{"resource":"artifact","action":"create"},{"resource":"tag","action":"create"},{"resource":"tag","action":"delete"}]'
  else
    access='[{"resource":"repository","action":"pull"},{"resource":"artifact","action":"read"}]'
  fi

  # Xóa robot cũ cùng tên nếu có (idempotent lab)
  local q="name%3D${PROJECT}%2B${short_name}"
  local existing
  existing="$("${CURL[@]}" "${HARBOR_URL}/api/v2.0/robots?q=${q}&page_size=10" || echo '[]')"
  local rid
  rid="$(echo "${existing}" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' | head -1)"
  if [[ -n "${rid}" ]]; then
    echo "    delete old robot id=${rid} (${PROJECT}+${short_name})"
    "${CURL[@]}" -X DELETE "${HARBOR_URL}/api/v2.0/robots/${rid}" >/dev/null || true
  fi

  local body
  body="$(cat <<EOF
{
  "name": "${short_name}",
  "duration": -1,
  "description": "npd-fineract ${short_name}",
  "disable": false,
  "level": "project",
  "permissions": [{
    "kind": "project",
    "namespace": "${PROJECT}",
    "access": ${access}
  }]
}
EOF
)"
  local resp
  resp="$("${CURL[@]}" -X POST "${HARBOR_URL}/api/v2.0/robots" \
    -H 'Content-Type: application/json' -d "${body}")"
  local secret name
  secret="$(echo "${resp}" | sed -n 's/.*"secret"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
  name="$(echo "${resp}" | sed -n 's/.*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
  if [[ -z "${secret}" ]]; then
    echo "ERROR create robot ${short_name}: ${resp}"
    exit 1
  fi
  echo "ROBOT_NAME_${short_name//-/_}=${name}"
  echo "ROBOT_SECRET_${short_name//-/_}=${secret}"
}

echo "==> robot k8s-pull (pull only)"
create_robot k8s-pull false
echo "==> robot ci-push (pull+push)"
create_robot ci-push true

echo
echo "Done. Export tokens rồi chạy vault-seed:"
echo "  export HARBOR_PULL_TOKEN='<ROBOT_SECRET_k8s_pull>'"
echo "  export HARBOR_PUSH_TOKEN='<ROBOT_SECRET_ci_push>'"
echo "  export REGISTRY=npd-harbor.co"
echo "  # rồi: bash scripts/vault-seed-fineract.sh  (trong vault-0 hoặc với vault CLI)"
