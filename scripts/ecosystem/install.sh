#!/usr/bin/env bash
# Cài Fineract ecosystem runner (song song npd-ecosystem banking).
#   sudo bash install.sh
#   ECOSYSTEM_ROOT=/other/path sudo bash install.sh
set -euo pipefail

ROOT="${ECOSYSTEM_ROOT:-/home/sysadmin/npd-fineract-ecosystem}"
REPO_SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
RUN_USER="${ECOSYSTEM_USER:-sysadmin}"

echo "==> Install dir: ${ROOT}"
mkdir -p "${ROOT}/bin" "${ROOT}/data" "${ROOT}/logs"

for f in common.py job_seed.py job_volume_txn.py job_bpm_onboard.py job_bpm_loan.py; do
  cp -f "${REPO_SCRIPTS}/${f}" "${ROOT}/bin/${f}"
done

if [[ ! -f "${ROOT}/.env" ]]; then
  cp "${REPO_SCRIPTS}/config.env.example" "${ROOT}/.env"
  sed -i "s|^DATA_DIR=.*|DATA_DIR=${ROOT}/data|" "${ROOT}/.env"
  sed -i "s|^LOG_DIR=.*|LOG_DIR=${ROOT}/logs|" "${ROOT}/.env"
  echo "Created ${ROOT}/.env — chỉnh FINERACT_URL / USER / PASSWORD / CURRENCY"
else
  echo "Keep existing ${ROOT}/.env"
fi

if [[ ! -x "${ROOT}/venv/bin/python" ]] || [[ ! -e "${ROOT}/venv/bin/pip" && ! -e "${ROOT}/venv/bin/pip3" ]]; then
  echo "==> (Re)create venv at ${ROOT}/venv"
  rm -rf "${ROOT}/venv"
  if ! python3 -m venv "${ROOT}/venv"; then
    echo "FAIL: python3 -m venv — cài: apt install -y python3-venv python3-pip"
    exit 1
  fi
fi
PY="${ROOT}/venv/bin/python"
"$PY" -m ensurepip --upgrade 2>/dev/null || true
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r "${REPO_SCRIPTS}/requirements.txt"

cat > "${ROOT}/bin/run-job.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT="${ROOT}"
export FINERACT_ECO_ENV="\${FINERACT_ECO_ENV:-\$ROOT/.env}"
JOB="\${1:?job name: seed|volume|bpm-onboard|bpm-loan}"
LOG_DIR="\$ROOT/logs"
mkdir -p "\$LOG_DIR"
TS="\$(date +%Y%m%d-%H%M%S)"
case "\$JOB" in
  seed)        PY=job_seed.py ;;
  volume)      PY=job_volume_txn.py ;;
  bpm-onboard) PY=job_bpm_onboard.py ;;
  bpm-loan)    PY=job_bpm_loan.py ;;
  *) echo "unknown job: \$JOB"; exit 2 ;;
esac
exec >>"\${LOG_DIR}/\${JOB}-\${TS}.log" 2>&1
echo "==== \$(date -Is) start \${JOB} ===="
cd "\$ROOT"
set -a
# shellcheck disable=SC1091
source "\$FINERACT_ECO_ENV"
set +a
set +e
"\${ROOT}/venv/bin/python" "\${ROOT}/bin/\${PY}"
rc=\$?
set -e
echo "==== \$(date -Is) end \${JOB} rc=\${rc} ===="
exit "\$rc"
EOF
chmod +x "${ROOT}/bin/run-job.sh"

# Log: mỗi lần chạy 1 file timestamp → dọn file cũ (không dùng logrotate rename).
# Giữ 7 ngày; chạy hàng ngày + có thể gọi tay: bin/cleanup-logs.sh
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-7}"
cat > "${ROOT}/bin/cleanup-logs.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
LOG_DIR="${ROOT}/logs"
DAYS="${LOG_RETENTION_DAYS}"
mkdir -p "\$LOG_DIR"
# xóa *.log / *.log.gz cũ hơn DAYS ngày
deleted=\$(find "\$LOG_DIR" -type f \\( -name '*.log' -o -name '*.log.gz' \\) -mtime +"\$DAYS" -print -delete | wc -l)
echo "\$(date -Is) cleanup-logs: removed \$deleted file(s) older than \$DAYS days in \$LOG_DIR"
EOF
chmod +x "${ROOT}/bin/cleanup-logs.sh"

# logrotate: nén file còn lại nếu ai đó đổi sang append cùng tên (phòng xa)
LOGROTATE_FILE=/etc/logrotate.d/npd-fineract-ecosystem
cat > "${LOGROTATE_FILE}" <<EOF
${ROOT}/logs/*.log {
    daily
    rotate ${LOG_RETENTION_DAYS}
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
    dateext
    maxage ${LOG_RETENTION_DAYS}
}
EOF
chmod 644 "${LOGROTATE_FILE}"

if id "${RUN_USER}" &>/dev/null; then
  chown -R "${RUN_USER}:${RUN_USER}" "${ROOT}"
fi

CRON_FILE=/etc/cron.d/npd-fineract-ecosystem
cat > "${CRON_FILE}" <<EOF
# NPD Fineract ecosystem — Instana V1–V3 / B1–B3 (${ROOT})
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""

# Seed bổ sung — Chủ nhật 04:00 (sau banking seed 03:00)
0 4 * * 0 ${RUN_USER} ${ROOT}/bin/run-job.sh seed

# Volume transfer/deposit/withdraw — mỗi phút (~theo giây trong job)
* * * * * ${RUN_USER} ${ROOT}/bin/run-job.sh volume

# BPM onboard — mỗi 5 phút
*/5 * * * * ${RUN_USER} ${ROOT}/bin/run-job.sh bpm-onboard

# BPM loan originate + repay — mỗi 5 phút (lệch :02)
2-57/5 * * * * ${RUN_USER} ${ROOT}/bin/run-job.sh bpm-loan

# Xóa log cũ hơn ${LOG_RETENTION_DAYS} ngày (tránh đầy đĩa — volume tạo ~1 file/phút)
30 3 * * * ${RUN_USER} ${ROOT}/bin/cleanup-logs.sh >${ROOT}/logs/cleanup-last.txt 2>&1
EOF
chmod 644 "${CRON_FILE}"

# Đảm bảo cron daemon chạy
if command -v systemctl >/dev/null 2>&1; then
  systemctl enable cron 2>/dev/null || systemctl enable crond 2>/dev/null || true
  systemctl start cron 2>/dev/null || systemctl start crond 2>/dev/null || true
fi

# Chạy cleanup một lần ngay (dọn sẵn nếu đã đầy)
"${ROOT}/bin/cleanup-logs.sh" || true

echo
echo "==== crontab đã cài ===="
cat "${CRON_FILE}"
echo "========================"
echo "logrotate: ${LOGROTATE_FILE} (rotate ${LOG_RETENTION_DAYS}d + maxage)"
echo "cleanup:   ${ROOT}/bin/cleanup-logs.sh (cron 03:30 daily)"
echo
echo "OK. Tiếp theo:"
echo "  1. vi ${ROOT}/.env"
echo "  2. ${ROOT}/bin/run-job.sh seed          # lần đầu bắt buộc"
echo "  3. cron tự chạy volume / bpm sau đó"
echo "  4. tail -f ${ROOT}/logs/*.log"
echo "  5. ls -l ${CRON_FILE}"
