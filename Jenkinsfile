// Jenkins Multibranch — nhánh dev-k8s
// Library: platform@main (catalog project npd-fineract)
// Flow: Kaniko mirror openmf → Harbor → bump deploy/dev-k8s/values/values-images.yaml → Argo

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
