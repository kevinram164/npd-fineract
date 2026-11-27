# Fineract ecosystem — synthetic teller (Instana)

Cùng kiểu `banking-demo/scripts/ecosystem` (server `sysadmin` + cron).  
Gọi API `https://npd-fineract.co/fineract-provider/api/v1` với header nghiệp vụ.

| Job | Script | Cron | Kịch bản |
|-----|--------|------|----------|
| Seed | `job_seed.py` | CN 04:00 | product + ~1000 client / 400 savings / 150 loan |
| Volume | `job_volume_txn.py` | mỗi phút | **V1** transfer · **V2** deposit · **V3** withdraw |
| BPM onboard | `job_bpm_onboard.py` | mỗi 5′ | **B1** create→savings→deposit |
| BPM loan | `job_bpm_loan.py` | mỗi 5′ (:02) | **B2** apply→approve→disburse · **B3** repay |

Header mỗi request:

- `X-Correlation-ID` — UUID (BPM giữ **cùng ID** xuyên bước)
- `X-Business-Flow` — `txn.transfer` / `txn.deposit` / `txn.withdraw` / `bpm.client.onboard` / `bpm.loan.origination` / `bpm.loan.repay`
- `X-Business-Step` — bước con
- `Idempotency-Key` — UUID (POST)

Auth lab: Basic `mifos` / `password`, tenant `default`.

---

## Deploy trên server giả lập

```bash
# copy repo hoặc scp thư mục scripts/ecosystem
cd npd-fineract/scripts/ecosystem
sudo bash install.sh

vi /home/sysadmin/npd-fineract-ecosystem/.env
# FINERACT_URL=https://npd-fineract.co/fineract-provider/api/v1
# FINERACT_CURRENCY=USD   # hoặc VND nếu tenant đã enable

/home/sysadmin/npd-fineract-ecosystem/bin/run-job.sh seed
/home/sysadmin/npd-fineract-ecosystem/bin/run-job.sh volume
/home/sysadmin/npd-fineract-ecosystem/bin/run-job.sh bpm-onboard
/home/sysadmin/npd-fineract-ecosystem/bin/run-job.sh bpm-loan
```

Log job: `/home/sysadmin/npd-fineract-ecosystem/logs/<job>-<ts>.log`  
State: `data/state.json`, `data/clients.json`

**Log retention:** `install.sh` cài  
- cron `cleanup-logs.sh` lúc 03:30 — **xóa `*.log` / `*.log.gz` > 7 ngày**  
- `/etc/logrotate.d/npd-fineract-ecosystem` — daily rotate + `maxage 7`  
Đổi số ngày: `LOG_RETENTION_DAYS=14 sudo bash install.sh`

Chạy tay không qua wrapper (dev):

```bash
cd npd-fineract/scripts/ecosystem
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp config.env.example .env
.venv/bin/python job_seed.py
```

---

## Kiểm tra từng kịch bản

### 1) Log trên server giả lập

```bash
tail -f /home/sysadmin/npd-fineract-ecosystem/logs/volume-*.log
grep -E 'corr=|FAIL|ok' /home/sysadmin/npd-fineract-ecosystem/logs/bpm-*.log | tail -50
```

Mỗi dòng OK có `corr=<uuid>` — dùng để tra Instana / pod log.

### 2) Log pod Fineract

```bash
kubectl -n npd-fineract logs -l app.kubernetes.io/name=fineract-server -f --tail=100
# hoặc grep correlation (cần FINERACT_LOGGING_HTTP_CORRELATION_ID_ENABLED=true)
kubectl -n npd-fineract logs -l app.kubernetes.io/name=fineract-server --tail=500 | grep '<uuid>'
```

### 3) Instana — Traces / Calls

1. **Applications** → service `fineract-server`
2. **Calls / Traces** — filter thời gian vừa chạy job
3. Endpoint gợi ý:
   - V1: `/accounttransfers`
   - V2/V3: `/savingsaccounts/.../transactions`
   - B1: `/clients`, `/savingsaccounts`
   - B2: `/loans` (+ `?command=approve|disburse`)
   - B3: `/loans/.../transactions`

### 4) Instana — Logs

**Analytics → Logs** → filter `service.name:fineract-server` + Trace ID (copy từ Call) hoặc text UUID `corr`.

### 5) Grafana + Telegram alerts

Dashboard: **NPD Fineract** (folder NPD) — RPS / 5xx / BPM URI / Hikari / heap.  
Alerts (`team=fineract` → Telegram): transfer lỗi, loan BPM lỗi, savings txn lỗi, 5xx, pool DB, heap, pod down.

```bash
# sau khi sync observability-monitoring-config + kube-prometheus-stack
# Target scrape: ServiceMonitor fineract-server → /fineract-provider/actuator/prometheus
kubectl -n monitoring get servicemonitor fineract-server
kubectl -n monitoring get prometheusrule npd-fineract-alerts
```

### 6) Instana — BPM Analyst

Dùng **B1 / B2 / B3** (đa bước + cùng `X-Correlation-ID`).  
Map process theo `X-Business-Step` / path. Volume V* không cần BPM.

### 7) Tra cứu data Fineract

| Cần | Cách |
|-----|------|
| Client / savings / loan id | `data/clients.json` hoặc UI https://npd-mifos.co |
| API | `GET .../clients/{id}`, `.../savingsaccounts/{id}`, `.../loans/{id}` |
| Correlation → resource | log job `corr=` rồi GET theo id in cùng dòng |

### Checklist OK

| ID | OK khi |
|----|--------|
| V1–V3 | `volume-*.log` nhiều `ok txn.*`; Instana Calls dày |
| B1 | `bpm-onboard` in `ok client=… savings=… corr=` |
| B2 | `originate ok loan=…` cùng một `corr` cho apply/approve/disburse |
| B3 | `repay ok loan=…` |

### Sự cố nhanh

```
corr UUID (từ log job)
  → Instana Trace / Analytics Logs
  → kubectl logs | grep UUID
  → GET resourceId trong Fineract
```

---

## Gợi ý tài nguyên

Cùng server với `npd-ecosystem` banking: 2–4 vCPU / 4–8 GB ổn.  
Volume mỗi phút + banking peer 10′ — theo dõi CPU Postgres HA và heap `fineract-server`.
