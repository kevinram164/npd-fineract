# NPD Fineract — kế hoạch triển khai (giống banking-demo / npd-shop)

Repo fork từ [Apache Fineract](https://github.com/apache/fineract) (Apache-2.0).  
GitOps trên `npd-k8s`: Helm + Argo CD + Jenkins + Vault + Harbor + Instana/Grafana — **tái dụng platform**.

| | |
|--|--|
| **Repo** | `https://github.com/kevinram164/npd-fineract.git` |
| **Nhánh** | `dev-k8s` |
| **Namespace** | `npd-fineract` |
| **Harbor** | `npd-harbor.co/npd-fineract/...` |
| **Tham chiếu** | `banking-demo` `dev-k8s`, `npd-shop` `deploy/dev-k8s`, `cloud-native-platform` |

---

## Thứ tự đúng (bắt buộc)

Giống banking/shop: **không** apply Argo trước khi Harbor + Vault (+ pull-secret) sẵn. Jenkins image có thể tạm bỏ qua nếu chart còn pull `openmf/*` từ Docker Hub.

```
① Harbor project + robot
② Vault seed + role fineract-app
③ harbor-pull-creds (ns npd-fineract)
④ Jenkins Multibranch / mirror image  (có thể song song sau ③)
⑤ Argo AppProject + app-of-apps
⑥ Observability (OTel Java / Instana AP)
```

| Bước | Việc | Script |
|------|------|--------|
| **1** | Project Harbor `npd-fineract`, robot `k8s-pull` + `ci-push` | `scripts/harbor-setup-project.sh` |
| **2** | KV `secret/fineract/{db,harbor,harbor-pull}` + policy/role | `scripts/vault-seed-fineract.sh` → `vault-setup-k8s-auth.sh` |
| **3** | Secret `harbor-pull-creds` | `create-harbor-pull-secret.sh` (`VAULT_PATH=secret/fineract/harbor-pull`) |
| **4** | Job Jenkins + catalog `npd-fineract` trong shared library | UI Jenkins + Dockerfile mirror |
| **5** | Sync chart (Postgres in-ns + server + web) | `deploy/dev-k8s/argocd/*` |

---

## Platform dùng chung vs riêng

### Đã có — không cài lại

Jenkins + `platform@main`, Harbor, Argo CD, Vault + Injector, OTel Collector, Instana agent, Prometheus/Grafana, Ingress HAProxy / f5-lb `10.100.1.100`.

### Riêng Fineract

| Item | Ghi chú |
|------|---------|
| Ns `npd-fineract` | RBAC / Vault role |
| Harbor project | `npd-fineract` |
| Vault | `secret/fineract/*`, role `fineract-app` ← SA `fineract-server` |
| Postgres | **In-chart** lab (`fineractdb`) — không share schema banking |
| Chart | `charts/fineract` |

Không cần RabbitMQ / Redis / Kong / Kafka banking lúc đầu.

---

## Kiến trúc CD

```
Developer push → Jenkins (platformPipeline / Kaniko)
                      │
                      ▼
              Harbor npd-fineract/*
                      │
         bump deploy/dev-k8s/values/values-images.yaml
                      │
                      ▼
              Argo CD (fineract-root-dev-k8s)
                      │
                      ▼
         ns npd-fineract: fineract-server + web-app + Postgres
                      │
         OTel → collector.observability:4317 → Instana
```

---

## Vault

```
secret/fineract/db            # JDBC user/pass (lab + sau này Agent inject)
secret/fineract/harbor-pull   # robot$npd-fineract+k8s-pull
secret/fineract/harbor        # robot$npd-fineract+ci-push  (Kaniko)
```

Role `fineract-app` bind SA `fineract-server` @ `npd-fineract` (trong `vault-setup-k8s-auth.sh`).  
Bật inject: `deploy/dev-k8s/values/values-vault.yaml` → `vault.enabled: true` (sau khi secret seed OK).

---

## Checklist

- [x] Repo GitHub + nhánh `dev-k8s`
- [ ] **Bước 1** Harbor project + robot
- [ ] **Bước 2** Vault seed + `fineract-app`
- [ ] **Bước 3** `harbor-pull-creds`
- [ ] **Bước 4** Jenkins + Dockerfile / mirror image
- [ ] **Bước 5** Argo sync Healthy; login `mifos`/`password`
- [ ] OTel Java agent + Instana AP `npd-fineract`

---

## Rủi ro

- Build Fineract (Gradle) nặng — ưu tiên mirror `openmf/fineract` vào Harbor trước, CI từ source sau.
- Ingress class NPD = **`haproxy`** (không dùng `nginx`).
- License Apache-2.0: giữ NOTICE/LICENSE.
