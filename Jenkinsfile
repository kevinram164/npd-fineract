// npd-fineract CI:
// - fineract-server: Gradle bootJar cần Docker (QueryDSL Testcontainers)
//   → container gradle + DinD sidecar, rồi Kaniko đóng JAR vào runtime image
// - web-app: Kaniko mirror openmf/web-app
// Expect fineract-server: 20–60 phút lần đầu.
@Library('platform@main') _

def cfg = com.platform.PipelineConfig.mergeDefaults([
  project             : 'npd-fineract',
  harborHost          : 'npd-harbor.co',
  harborProject       : 'npd-fineract',
  gitBranch           : 'dev-k8s',
  gitRepoUrl          : 'https://github.com/kevinram164/npd-fineract.git',
  gitopsValuesFile    : 'deploy/dev-k8s/values/values-images.yaml',
  kanikoSkipTlsVerify : true,
  kanikoUseCache      : false,
  vaultAddr           : 'http://vault.vault.svc.cluster.local:8200',
  vaultRole           : 'jenkins-kaniko',
  vaultHarborPath     : 'fineract/harbor',
  vaultGithubPath     : 'platform/github',
])

properties([
  parameters([
    choice(
      name: 'BUILD_TARGET',
      choices: com.platform.ChangeDetector.buildTargetChoices(cfg),
      description: 'auto | all | fineract-server | web-app',
    ),
  ]),
])

podTemplate(
  yamlMergeStrategy: merge(),
  yaml: """
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins-kaniko
  containers:
    - name: jnlp
      env:
        - name: HOME
          value: /home/jenkins/agent
      workingDir: /home/jenkins/agent
      volumeMounts:
        - name: home-jenkins
          mountPath: /home/jenkins
    - name: dind
      image: docker:27-dind
      securityContext:
        privileged: true
      env:
        - name: DOCKER_TLS_CERTDIR
          value: ""
      resources:
        requests:
          memory: "1Gi"
          cpu: "200m"
        limits:
          memory: "4Gi"
          cpu: "2"
      volumeMounts:
        - name: dind-storage
          mountPath: /var/lib/docker
    - name: gradle
      image: eclipse-temurin:25-jdk
      command: ["sleep"]
      args: ["99d"]
      tty: true
      resources:
        requests:
          memory: "4Gi"
          cpu: "500m"
        limits:
          memory: "8Gi"
          cpu: "4"
      env:
        - name: GRADLE_OPTS
          value: "-Dorg.gradle.daemon=false -Dorg.gradle.workers.max=2 -Xmx4g"
        - name: DOCKER_HOST
          value: "tcp://localhost:2375"
        - name: TESTCONTAINERS_HOST_OVERRIDE
          value: "localhost"
        - name: TESTCONTAINERS_RYUK_DISABLED
          value: "true"
        - name: DOCKER_API_VERSION
          value: "1.44"
      volumeMounts:
        - name: home-jenkins
          mountPath: /home/jenkins
        - name: workspace-volume
          mountPath: /home/jenkins/agent
      workingDir: /home/jenkins/agent
    - name: kaniko
      image: ${cfg.kanikoImage}
      command: ["/busybox/busybox"]
      args:
        - "sh"
        - "-c"
        - "mkdir -p /home/jenkins/agent/bin && cp /busybox/busybox /home/jenkins/agent/bin/sh && cp /busybox/busybox /home/jenkins/agent/bin/busybox && exec /busybox/busybox sleep 99d"
      tty: true
      resources:
        requests:
          memory: "1Gi"
          cpu: "200m"
        limits:
          memory: "4Gi"
          cpu: "2"
      env:
        - name: PATH
          value: "/home/jenkins/agent/bin:/busybox:/kaniko:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
      securityContext:
        runAsUser: 0
        runAsGroup: 0
        runAsNonRoot: false
        allowPrivilegeEscalation: false
      volumeMounts:
        - name: home-jenkins
          mountPath: /home/jenkins
        - name: workspace-volume
          mountPath: /home/jenkins/agent
      workingDir: /home/jenkins/agent
  volumes:
    - name: home-jenkins
      emptyDir: {}
    # workspace-volume: Jenkins Kubernetes plugin injects via yamlMergeStrategy merge()
    - name: dind-storage
      emptyDir: {}
""") {
  node(POD_LABEL) {
    def targets = []
    try {
      stage('Checkout') {
        checkout scm
        env.GIT_COMMIT = sh(script: 'git rev-parse HEAD', returnStdout: true).trim()
      }

      targets = com.platform.ChangeDetector.resolve(this, cfg)
      notifyTelegram.send(this, cfg, 'started', [
        buildTarget: params.BUILD_TARGET,
        services   : targets,
      ])

      if (targets.isEmpty()) {
        echo 'No services selected — done.'
        currentBuild.result = 'SUCCESS'
        notifyTelegram.send(this, cfg, 'success', [buildTarget: params.BUILD_TARGET, services: []])
        return
      }

      if (targets.contains('fineract-server')) {
        stage('Gradle fineract-server') {
          container('gradle') {
            sh '''
              set -e
              export DEBIAN_FRONTEND=noninteractive
              # Docker CLI → DinD sidecar
              if ! command -v docker >/dev/null 2>&1; then
                apt-get update -qq
                apt-get install -y -qq docker.io curl ca-certificates >/dev/null
              fi
              echo "Waiting for DinD..."
              for i in $(seq 1 60); do
                if docker info >/dev/null 2>&1; then
                  echo "DinD ready"
                  break
                fi
                if [ "$i" -eq 60 ]; then
                  echo "DinD not reachable on tcp://localhost:2375"
                  exit 1
                fi
                sleep 2
              done
              docker version

              # QueryDSL codegen: Postgres qua docker run + JDBC (bỏ Testcontainers — hay fail trên DinD)
              docker rm -f querydsl-pg >/dev/null 2>&1 || true
              docker pull postgres:17-alpine
              docker run -d --name querydsl-pg \
                -e POSTGRES_USER=test \
                -e POSTGRES_PASSWORD=test \
                -e POSTGRES_DB=test \
                -p 54329:5432 \
                postgres:17-alpine
              echo "Waiting for querydsl-pg..."
              for i in $(seq 1 60); do
                if docker exec querydsl-pg pg_isready -U test -d test >/dev/null 2>&1; then
                  echo "querydsl-pg ready"
                  break
                fi
                if [ "$i" -eq 60 ]; then
                  docker logs querydsl-pg || true
                  echo "querydsl-pg not ready"
                  exit 1
                fi
                sleep 2
              done
              export QUERYDSL_JDBC_URL='jdbc:postgresql://localhost:54329/test'
              export QUERYDSL_JDBC_USER=test
              export QUERYDSL_JDBC_PASSWORD=test

              chmod +x ./gradlew
              ./gradlew --no-daemon --console=plain --stacktrace \
                :fineract-provider:bootJar \
                -x test -x cucumber -x rat \
                -x spotlessJava -x spotlessJavaCheck \
                -x buildJavaSdk
              JAR=$(ls fineract-provider/build/libs/fineract-provider*.jar | grep -v plain | head -1)
              cp "$JAR" docker/fineract-server/fineract-provider.jar
              ls -lh docker/fineract-server/fineract-provider.jar
              docker rm -f querydsl-pg >/dev/null 2>&1 || true
            '''
          }
        }
        stage('Kaniko fineract-server') {
          def meta = (cfg.services['fineract-server'] ?: [:]) + [
            context     : 'docker/fineract-server',
            dockerfile  : 'Dockerfile',
            snapshotMode: 'full',
          ]
          def cfgJar = cfg + [services: (cfg.services + ['fineract-server': meta])]
          com.platform.KanikoBuilder.buildAndPush(this, cfgJar, 'fineract-server')
        }
      }

      if (targets.contains('web-app')) {
        stage('Build web-app') {
          com.platform.KanikoBuilder.buildAndPush(this, cfg, 'web-app')
        }
      }

      stage('Update GitOps') {
        com.platform.GitOpsUpdater.bumpImageTags(this, cfg, targets)
      }

      currentBuild.result = 'SUCCESS'
      notifyTelegram.send(this, cfg, 'success', [
        buildTarget: params.BUILD_TARGET,
        services   : targets,
      ])
    } catch (Exception e) {
      def aborted = (e.class?.name ?: '').contains('FlowInterrupted') ||
        (e.message ?: '').toLowerCase().contains('aborted')
      currentBuild.result = aborted ? 'ABORTED' : 'FAILURE'
      notifyTelegram.send(this, cfg, aborted ? 'aborted' : 'failure', [
        buildTarget: params.BUILD_TARGET,
        services   : targets,
        error      : e.message,
      ])
      throw e
    }
  }
}
