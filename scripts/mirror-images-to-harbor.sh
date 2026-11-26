#!/usr/bin/env bash
# Mirror openmf → Harbor (tag bootstrap) trước CI hoặc khi chưa có Multibranch.
# Cần: docker hoặc crane + login Harbor (robot ci-push).
#
#   export HARBOR_USER='robot$npd-fineract+ci-push'
#   export HARBOR_PASS='...'
#   bash scripts/mirror-images-to-harbor.sh
set -euo pipefail

REGISTRY="${REGISTRY:-npd-harbor.co}"
PROJECT="${HARBOR_PROJECT:-npd-fineract}"
TAG="${MIRROR_TAG:-bootstrap}"
: "${HARBOR_USER:?set HARBOR_USER}"
: "${HARBOR_PASS:?set HARBOR_PASS}"

login() {
  if command -v crane >/dev/null 2>&1; then
    echo "${HARBOR_PASS}" | crane auth login "${REGISTRY}" -u "${HARBOR_USER}" --password-stdin
  else
    echo "${HARBOR_PASS}" | docker login "${REGISTRY}" -u "${HARBOR_USER}" --password-stdin
  fi
}

copy() {
  local src="$1" dest="$2"
  echo "==> ${src} → ${dest}"
  if command -v crane >/dev/null 2>&1; then
    crane copy "${src}" "${dest}"
  else
    docker pull "${src}"
    docker tag "${src}" "${dest}"
    docker push "${dest}"
  fi
}

login
copy "openmf/fineract:develop" "${REGISTRY}/${PROJECT}/fineract-server:${TAG}"
copy "openmf/web-app:dev" "${REGISTRY}/${PROJECT}/web-app:${TAG}"
echo "OK. values-images.yaml tag=${TAG} — Argo sẽ pull từ Harbor."
