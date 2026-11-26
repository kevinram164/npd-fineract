# GitHub Actions — tắt trên fork NPD

CI/CD lab dùng **Jenkins** (`npd-jenkins.co`), không dùng GitHub Actions của upstream Apache Fineract.

Workflows gốc đã chuyển sang `workflows.upstream-disabled/` để Actions không chạy (tiết kiệm phút GHA + tránh fail PR).

Bật lại (không khuyến nghị trên fork lab):

```bash
mv .github/workflows.upstream-disabled .github/workflows
```
