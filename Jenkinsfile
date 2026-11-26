// CI: sửa code Java (fineract-*) → Kaniko multi-stage Gradle → Harbor → bump values-images → Argo
// UI web-app vẫn mirror openmf (không có source UI trong repo này).
// Lần đầu / force: BUILD_TARGET=fineract-server  (hoặc all). Expect 15–45 phút.

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
