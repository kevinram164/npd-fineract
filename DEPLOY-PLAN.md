# NPD Fineract — kế hoạch triển khai (giống banking-demo)

Repo fork nội bộ từ [Apache Fineract](https://github.com/apache/fineract) (Apache-2.0).  
Mục tiêu: GitOps trên `npd-k8s` giống `banking-demo` — Helm + Argo CD + Jenkins + Instana/Grafana, **tái dụng platform** tối đa.

| | |
|--|--|
| **Repo GitHub (dự kiến)** | `https://github.com/kevinram164/npd-fineract.git` |
| **Nhánh lab** | `dev-k8s` (sau bootstrap) |
| **Namespace** | `npd-fineract` |
| **Harbor** | `npd-harbor.co/npd-fineract/...` |
| **Tham chiếu** | `banking-demo` `dev-k8s`, `cloud-native-platform`, `LOGS-TO-INSTANA.md` |

---

## 1. Kiến trúc mục tiêu

```
Developer push → Jenkins (platformPipeline / Kaniko)
                      │
                      ▼
              Harbor npd-fineract/*
                      │
         bump deploy/dev-k8s/values/values-images.yaml
                      │
                      ▼
              Argo CD (app-of-apps fineract-*)
                      │
                      ▼
         ns npd-fineract: fineract-server + web-app + Postgres (lab)
                      │
         OTel / Instana Java agent → collector observability → Instana
         /metrics → Prometheus (UWM) → Grafana
```

Khác banking-demo: Fineract gần **1–2 workload JVM** (+ DB + UI), không phải nhiều microservice Python.

---

## 2. Platform — dùng chung vs riêng

### Dùng chung (đã có trên NPD — không cài lại)

| Thành phần | Ns / nơi | Cách Fineract dùng |
|------------|----------|-------------------|
| **Jenkins** + shared library `platform@main` | Jenkins platform | `Jenkinsfile` gọi `platformPipeline` (project=`npd-fineract`) |
| **Harbor** | `npd-harbor.co` | Project mới `npd-fineract` (tạo 1 lần) |
| **Argo CD** | `argocd` | AppProject + Application trỏ repo này |
| **Vault** + Agent Injector | `vault` | Role mới `fineract-app` + KV path (mục 4) |
| **OTel Collector** | `observability` | OTLP `:4317` → APM + Instana (đã có pipeline logs/traces) |
| **Instana agent** | `instana-agent` | OTLP ingest; JVM attach / OTel Java agent |
| **Prometheus / Grafana** | `monitoring` | ServiceMonitor trong ns app (UWM như banking) |
| **Ingress / DNS lab** | cluster | Host vd. `fineract.npd.co`, `mifos.npd.co` |
| **Keycloak** (tuỳ chọn sau) | platform | OAuth2 cho UI/API — phase 2 |

### Riêng cho Fineract (trong repo / ns app)

| Thành phần | Lý do |
|------------|--------|
| Namespace `npd-fineract` | Tách RBAC, Vault role, NetworkPolicy |
| Helm chart `charts/fineract` | Server + web-app (+ optional Postgres lab) |
| Postgres **riêng** (lab) hoặc DB ngoài | Fineract cần DB `fineract_tenants` + `fineract_default` — **không** share schema với `npd-banking` |
| Image build | Gradle/Jib hoặc Dockerfile từ upstream |
| Application Perspective Instana `npd-fineract` | Filter Dest Service Name |

### Không dùng / không bắt buộc lúc đầu

| Thành phần | Ghi chú |
|------------|---------|
| RabbitMQ / Redis banking | Fineract không cần stack messaging của banking-demo |
| Kong gateway banking | Có thể Ingress thẳng; Gateway sau nếu cần |
| Kafka Strimzi | Chỉ khi bật Fineract external events |

---

## 3. Phases triển khai

### Phase 0 — Repo & GitHub (bây giờ)

1. Tạo repo GitHub `kevinram164/npd-fineract` (private/public tuỳ bạn).  
2. Push `main` (đã set `origin`).  
3. Tạo nhánh `dev-k8s` từ `main`.  
4. Giữ NOTICE/LICENSE Apache; ghi `NOTICE-NPD.md` nếu fork có chỉnh NPD.

### Phase 1 — Helm + Argo (CD skeleton)

1. Hoàn thiện `charts/fineract` (Deployment/Service/Ingress/PVC).  
2. `deploy/dev-k8s/argocd/*` — AppProject `fineract`, app-of-apps, apps: namespace, postgres, server, webapp, ingress.  
3. `values-images.yaml` — tag image Harbor.  
4. Apply AppProject + root Application trên cluster (giống banking).

**Acceptance:** Argo sync Healthy; UI Mifos login `mifos`/`password` (lab).

### Phase 2 — Jenkins CI

1. Harbor project `npd-fineract` + robot account trong Vault (`platform/harbor` hoặc path riêng).  
2. `Jenkinsfile` dùng `platformPipeline` (điền `gitRepoUrl`, `harborProject`, `gitopsValuesFile`).  
3. Pipeline: build image Fineract (+ web-app nếu build từ source UI) → push Harbor → bump tag.

**Acceptance:** Commit → image mới → Argo cập nhật pod.

### Phase 3 — Secrets (Vault)

Xem mục 4.

### Phase 4 — Observability

1. **Traces/logs:**  
   - Ưu tiên lab: **OTel Java agent** → `opentelemetry-collector.observability:4317` (khớp banking).  
   - Hoặc Instana Java agent attach (nếu muốn sensor JVM sâu).  
2. Env: `OTEL_SERVICE_NAME=fineract-server`, resource attrs `k8s.namespace.name=npd-fineract`.  
3. `values-observability.yaml` + ServiceMonitor `/actuator/prometheus` nếu có.  
4. Grafana: dashboard JVM/HTTP (reuse stack monitoring).  
5. Instana AP: Dest Service = `fineract-server` (và web nếu có).

**Acceptance:** Analytics Calls + Logs có service Fineract; Grafana scrape được.

### Phase 5 — Nghiệp vụ & harden

1. Seed sản phẩm savings/loan, client demo.  
2. PVC StorageClass cluster (bỏ `hostPath` lab).  
3. NetworkPolicy, resource limits theo worker.  
4. (Tuỳ chọn) tích hợp Keycloak.

---

## 4. Vault — làm thế nào?

Giống banking: **Vault đã chạy sẵn**; chỉ thêm path + role + annotate SA.

### KV (đề xuất)

```
secret/fineract/db
  FINERACT_HIKARI_USERNAME
  FINERACT_HIKARI_PASSWORD
  FINERACT_HIKARI_JDBC_URL          # jdbc:postgresql://...
  FINERACT_DEFAULT_TENANTDB_PWD
  # ... các key Fineract cần
```

### Policy / role

| | banking (tham chiếu) | fineract |
|--|----------------------|----------|
| Role | `banking-app` | `fineract-app` |
| SA ns | `npd-banking` | `npd-fineract` |
| Inject | annotation Vault Agent trên Deployment | tương tự |

### Helm values (`values-vault.yaml`)

```yaml
global:
  vault:
    enabled: true
    role: fineract-app
    dbPath: secret/data/fineract/db
```

Template Deployment: annotation `vault.hashicorp.com/agent-inject` + template export env (copy pattern `banking-demo` `values-vault.yaml` + chart).

### Việc trên `cloud-native-platform`

1. Vault policy `fineract-app` đọc `secret/data/fineract/*`.  
2. K8s auth role bind SA `fineract-server` (và web nếu cần).  
3. Seed secret lab (script tương tự `instana` / banking seed).

**Không** nhét password Postgres vào Git.

---

## 5. So sánh nhanh với banking-demo

| | banking-demo | npd-fineract |
|--|--------------|--------------|
| Ngôn ngữ | Python FastAPI × N | Java Spring (Fineract) + UI |
| Chart | Umbrella nhiều subchart | 1 chart (server + web + db) |
| Jenkins | `platformPipeline` | Cùng library |
| GitOps | `deploy/dev-k8s` | Cùng layout |
| Vault | `secret/banking/*` | `secret/fineract/*` |
| OTel | SDK Python | Java agent / Micrometer OTLP |
| Instana filter | api-producer, … | fineract-server |
| DB | Postgres banking | Postgres Fineract **riêng** |

---

## 6. Cấu trúc thư mục NPD (đã scaffold)

```
npd-fineract/
  ├── (upstream Apache Fineract source)
  ├── charts/fineract/           # Helm
  ├── deploy/dev-k8s/
  │   ├── README.md
  │   ├── argocd/
  │   └── values/
  ├── Jenkinsfile
  ├── DEPLOY-PLAN.md             # file này
  └── NOTICE / LICENSE           # giữ Apache
```

---

## 7. Việc làm ngay (checklist)

- [ ] Tạo repo GitHub `npd-fineract`, `git push -u origin main`  
- [ ] `git checkout -b dev-k8s` && push  
- [ ] Harbor project `npd-fineract`  
- [ ] Vault path + role `fineract-app` (platform)  
- [ ] Apply Argo AppProject + app-of-apps  
- [ ] Phase 1 sync image upstream trước, Phase 2 mới build từ source  

---

## 8. Rủi ro / lưu ý

- Upstream Fineract build nặng (JDK mới, Gradle heap lớn) — CI cần agent đủ RAM hoặc dùng image `apache/fineract` / `openmf/fineract` giai đầu.  
- Manifest mifosx dùng `hostPath` — trên kubeadm NPD đổi sang StorageClass thật.  
- License Apache-2.0: giữ attribution khi fork.  
- Tab Log trong Application Perspective Instana có thể trống INFO — dùng Analytics → Logs (như banking).
