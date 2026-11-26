// Jenkinsfile — nhánh dev-k8s (pattern banking-demo)
// Shared library: https://github.com/kevinram164/jenkins-shared-library
// CD: bump tag trong deploy/dev-k8s/values/values-images.yaml → ArgoCD sync.
//
// Phase 2: bổ sung Dockerfile/Kaniko context cho fineract-server (Gradle/Jib).
// Ban đầu có thể deploy image upstream và chỉ dùng Argo (không cần Jenkins).

@Library('platform@main') _

platformPipeline([
  project              : 'npd-fineract',
  harborHost           : 'npd-harbor.co',
  harborProject        : 'npd-fineract',
  gitBranch            : 'dev-k8s',
  gitRepoUrl           : 'https://github.com/kevinram164/npd-fineract.git',
  gitopsValuesFile     : 'deploy/dev-k8s/values/values-images.yaml',
  kanikoSkipTlsVerify  : true,
  kanikoUseCache       : false,
  vaultAddr            : 'http://vault.vault.svc.cluster.local:8200',
  vaultRole            : 'jenkins-kaniko',
  vaultHarborPath      : 'fineract/harbor',
  vaultGithubPath      : 'platform/github',
])
