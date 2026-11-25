// =============================================================================
//  Jenkinsfile — oan_a2c (Frappe app). Single pipeline for the `oan-package`
//  GitHub Organization folder (multibranch).
//
//  Per branch (all publish to the ECR repo `eoan/oan-a2c-service/a2c-service`):
//    develop     -> build + push + ci/deploy-helm-dev.sh (helm upgrade --install of release `a2c`,
//                   namespace A2C_NAMESPACE, on the oan_dev k3s node, from a VPN deploy agent)
//                   + ci/deploy-gateway.sh (APISIX routes, chart apisix/k8s, only when the spec,
//                   apisix/ or the gateway values changed; same kubeconfig as the helm deploy)
//    staging     -> promotes what develop built from this same source tree: ci/package_chart.py promote tags the
//                   develop image <version>-staging.<build> and repackages its chart, a seed image is built
//                   from openg2p-data, then ci/deploy-helm-dev.sh (DEPLOY_ENV=staging, helm/environments/staging)
//                   and ci/deploy-gateway.sh install them on the QA cluster (qa.oanstaging.com). The chart is
//                   published to repository/staging of oan-helm. Nothing is rebuilt.
//
//  Tags:  <__version__>-<branch>.<build>, e.g. 0.0.1-develop.57 / 0.0.1-staging.58 (= chart version)
//
//  Agent needs: docker(+buildx), aws cli v2, git.
//  Credentials: AWS_ACCOUNT_ID (string), oan-dev-kubeconfig (file, oan-service-helm cluster/),
//               oan-qa-kubeconfig (file, the jenkins-qa-deployer ServiceAccount of oan-helm docs/qa-cluster.md; staging),
//  NOTE: `aws ecr get-login-password` uses the agent's ambient AWS identity, which
//        must have ECR push on `eoan/oan-a2c-service/a2c-service`.
// =============================================================================
pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '30'))
    timeout(time: 60, unit: 'MINUTES')
  }

  environment {
    AWS_REGION      = 'ap-south-1'
    FRAPPE_BRANCH   = 'version-16'
    FRAPPE_PATH     = 'https://github.com/frappe/frappe'
    A2C_NAMESPACE   = 'a2c'
  }

  stages {
    stage('Resolve') {
      steps {
        script {
          // One ECR repo for every branch: eoan/oan-a2c-service/a2c-service (must exist in ECR).
          // develop tag = chart version = <__version__>-develop.<build_number>, e.g. 0.0.1-develop.57
          // (ci/package_chart.py version); staging: <__version__>-staging.<build>.
          env.ECR_REPO      = 'eoan/oan-a2c-service/a2c-service'
          env.ECR_SEED_REPO = 'eoan/oan-a2c-service/a2c-seed'
          env.IMMUTABLE_TAG = "${env.BRANCH_NAME}-${env.BUILD_NUMBER}"
          if (env.BRANCH_NAME == 'develop' || env.BRANCH_NAME == 'staging') {
            env.IMMUTABLE_TAG = sh(returnStdout: true, script: 'python3 ci/package_chart.py version').trim()
          }
          env.MOVING_TAG    = "${env.BRANCH_NAME}-latest"
          echo "branch=${env.BRANCH_NAME}  repo=${env.ECR_REPO}  seed_repo=${env.ECR_SEED_REPO}  tag=${env.IMMUTABLE_TAG}"
        }
      }
    }

    stage('Build image') {
      when { branch 'develop' }
      steps {
        withCredentials([string(credentialsId: 'AWS_ACCOUNT_ID', variable: 'AWS_ACCOUNT_ID')]) {
          sh '''#!/usr/bin/env bash
            set -euo pipefail
            IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
            SEED_IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_SEED_REPO}"

            # Build seed container (carries demo data from openg2p-data and load.py). Pass the commit
            # openg2p-data develop points at: an unchanged build-arg would let the layer cache keep
            # serving an old clone after the data is fixed.
            OPENG2P_DATA_REF=$(git ls-remote https://github.com/Centre-for-Open-Societal-Systems/openg2p-data.git refs/heads/develop | cut -f1)
            test -n "${OPENG2P_DATA_REF}" || { echo "Could not resolve openg2p-data develop" >&2; exit 1; }
            echo "openg2p-data develop is ${OPENG2P_DATA_REF}"
            DOCKER_BUILDKIT=1 docker buildx build \
              --build-arg OPENG2P_DATA_REF=${OPENG2P_DATA_REF} \
              --tag ${SEED_IMAGE_URI}:${IMMUTABLE_TAG} \
              --tag ${SEED_IMAGE_URI}:${MOVING_TAG} \
              --load ci/seed
            echo "Built ${SEED_IMAGE_URI}:${IMMUTABLE_TAG}"

            rm -rf frappe_docker
            git clone --depth 1 https://github.com/frappe/frappe_docker.git frappe_docker

            AUTH_BRANCH="develop"

            # OAN Messaging connector (a required app), on the same branch as oan_auth_service.
            CONNECTOR_REPO="https://github.com/Centre-for-Open-Societal-Systems/oan_messaging_connector.git"

            printf '[{"url":"https://github.com/Centre-for-Open-Societal-Systems/oan_auth_service.git","branch":"%s"},{"url":"https://github.com/Centre-for-Open-Societal-Systems/oan_a2c_service.git","branch":"%s"},{"url":"%s","branch":"%s"}]' \
              "${AUTH_BRANCH}" "${BRANCH_NAME}" "${CONNECTOR_REPO}" "${AUTH_BRANCH}" > /tmp/apps.json

            cd frappe_docker
            DOCKER_BUILDKIT=1 docker buildx build \
              --build-arg FRAPPE_PATH=${FRAPPE_PATH} \
              --build-arg FRAPPE_BRANCH=${FRAPPE_BRANCH} \
              --secret id=apps_json,src=/tmp/apps.json \
              --tag ${IMAGE_URI}:${IMMUTABLE_TAG} \
              --tag ${IMAGE_URI}:${MOVING_TAG} \
              --file images/layered/Containerfile \
              --network=host --load .
            echo "Built ${IMAGE_URI}:${IMMUTABLE_TAG}"
          '''
        }
      }
    }

    stage('Push to ECR') {
      when { branch 'develop' }
      steps {
        withCredentials([string(credentialsId: 'AWS_ACCOUNT_ID', variable: 'AWS_ACCOUNT_ID')]) {
          sh '''#!/usr/bin/env bash
            set -euo pipefail
            REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
            IMAGE_URI="${REGISTRY}/${ECR_REPO}"
            SEED_IMAGE_URI="${REGISTRY}/${ECR_SEED_REPO}"

            aws ecr get-login-password --region ${AWS_REGION} \
              | docker login --username AWS --password-stdin "${REGISTRY}"

            # Create repositories if missing
            aws ecr describe-repositories --region ${AWS_REGION} --repository-names "${ECR_REPO}" >/dev/null 2>&1 \
              || aws ecr create-repository --region ${AWS_REGION} --repository-name "${ECR_REPO}" >/dev/null

            aws ecr describe-repositories --region ${AWS_REGION} --repository-names "${ECR_SEED_REPO}" >/dev/null 2>&1 \
              || aws ecr create-repository --region ${AWS_REGION} --repository-name "${ECR_SEED_REPO}" >/dev/null

            docker push ${IMAGE_URI}:${IMMUTABLE_TAG}
            docker push ${IMAGE_URI}:${MOVING_TAG}       # same digest -> ECR dedups

            docker push ${SEED_IMAGE_URI}:${IMMUTABLE_TAG}
            docker push ${SEED_IMAGE_URI}:${MOVING_TAG}

            # Scoped cleanup ONLY. Never `docker system prune -f` on a shared agent:
            # it wipes other jobs' caches/images and can break concurrent builds.
            docker rmi ${IMAGE_URI}:${IMMUTABLE_TAG} ${IMAGE_URI}:${MOVING_TAG} \
                       ${SEED_IMAGE_URI}:${IMMUTABLE_TAG} ${SEED_IMAGE_URI}:${MOVING_TAG} || true
            echo "Pushed ${IMAGE_URI}:${IMMUTABLE_TAG} and ${SEED_IMAGE_URI}:${IMMUTABLE_TAG}"
          '''
        }
      }
    }

    // staging: the seed is the one image built here. It comes from openg2p-data develop, like develop's, and carries the
    // staging version so the chart's seed tag (ci/deploy-helm-dev.sh sets it) finds it.
    stage('Seed image (staging)') {
      when { branch 'staging' }
      steps {
        withCredentials([string(credentialsId: 'AWS_ACCOUNT_ID', variable: 'AWS_ACCOUNT_ID')]) {
          sh '''#!/usr/bin/env bash
            set -euo pipefail
            REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
            SEED_IMAGE_URI="${REGISTRY}/${ECR_SEED_REPO}"
            OPENG2P_DATA_REF=$(git ls-remote https://github.com/Centre-for-Open-Societal-Systems/openg2p-data.git refs/heads/develop | cut -f1)
            test -n "${OPENG2P_DATA_REF}" || { echo "Could not resolve openg2p-data develop" >&2; exit 1; }
            echo "openg2p-data develop is ${OPENG2P_DATA_REF}"
            DOCKER_BUILDKIT=1 docker buildx build \
              --build-arg OPENG2P_DATA_REF=${OPENG2P_DATA_REF} \
              --tag ${SEED_IMAGE_URI}:${IMMUTABLE_TAG} \
              --load ci/seed
            aws ecr get-login-password --region ${AWS_REGION} \
              | docker login --username AWS --password-stdin "${REGISTRY}"
            aws ecr describe-repositories --region ${AWS_REGION} --repository-names "${ECR_SEED_REPO}" >/dev/null 2>&1 \
              || aws ecr create-repository --region ${AWS_REGION} --repository-name "${ECR_SEED_REPO}" >/dev/null
            docker push ${SEED_IMAGE_URI}:${IMMUTABLE_TAG}
            docker rmi ${SEED_IMAGE_URI}:${IMMUTABLE_TAG} || true
          '''
        }
      }
    }

    // Flow (develop): Resolve (version) -> Build image -> Push to ECR -> Package chart -> deploy -> Publish chart.
    // helm/oan-a2c-service is zipped with this build's image before the deploy; the deploy uses the
    // same version tag, and the same archive is published to oan-helm afterwards.
    // ---------------------- Helm chart package (same name as the image) ----------------------
    // staging: `promote` instead of `package`: the chart develop built from this source tree, its image tagged for staging.
    stage('Package chart') {
      when { anyOf { branch 'develop'; branch 'staging' } }
      steps {
        withCredentials([string(credentialsId: 'AWS_ACCOUNT_ID', variable: 'AWS_ACCOUNT_ID')]) {
          script {
            env.IMAGE_TAG = env.IMMUTABLE_TAG
            env.SOURCE_COMMIT = sh(returnStdout: true, script: 'git rev-parse --verify HEAD').trim()
            env.COMMIT_SUBJECT = sh(returnStdout: true, script: 'git log -1 --pretty=%s').trim()
            env.IMAGE_REPOSITORY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
          }
          script {
              if (env.BRANCH_NAME == 'staging') {
                  // The workspace holds the staging branch only; promote needs the develop commits the chart index names.
                  withCredentials([gitUsernamePassword(credentialsId: scm.userRemoteConfigs[0].credentialsId, gitToolName: 'Default')]) {
                      sh 'git fetch --quiet --no-tags origin +refs/heads/develop:refs/remotes/origin/develop'
                  }
              }
          }
          sh "python3 ci/package_chart.py ${env.BRANCH_NAME == 'staging' ? 'promote' : 'package'}"
        }
        // The deploy stages run on the VPN deploy agent, which gets the archive from here.
        stash name: 'built-chart', includes: 'built-chart/**'
      }
    }

    // The routes chart (apisix/k8s) is packaged and published like the app chart, but only for a build that
    // changed the spec, the routes or the gateway values: those are the builds that install it.
    stage('Package gateway chart') {
      when {
        beforeAgent true
        anyOf {
          branch 'staging'
          allOf {
            branch 'develop'
            anyOf {
              changeset 'apisix/**'
              changeset 'openapi/**'
              changeset 'helm/environments/dev/oan-a2c-gateway.yaml'
            }
          }
        }
      }
      steps {
        sh 'python3 ci/package_chart.py gateway-package'
        stash name: 'built-gateway-chart', includes: 'built-gateway-chart/**'
      }
    }

    // ---------------------- per-branch deploy ----------------------

    // develop -> Helm release `a2c` on the oan_dev k3s node, from the archive 'Package chart' built.
    // First run installs, later runs upgrade; the chart generates its admin, secret-key and JWT Secrets.
    stage('develop → oan_dev (helm)') {
      when { beforeAgent true; branch 'develop' }
      agent { label 'oan-ci-deploy' }   // VPN agent with helm and kubectl that reaches the oan_dev API
      options { timeout(time: 45, unit: 'MINUTES') }
      steps {
        checkout scm
        unstash 'built-chart'
        withCredentials([file(credentialsId: 'oan-dev-kubeconfig', variable: 'KUBECONFIG')]) {
          sh 'bash ci/deploy-helm-dev.sh'
        }
      }
    }

    // develop -> APISIX routes (chart apisix/k8s) on the oan_dev node, after the app deploy.
    // Runs only when the spec, the generated routes or the gateway values changed.
    stage('develop → gateway (apisix)') {
      when {
        beforeAgent true
        allOf {
          branch 'develop'
          anyOf {
            changeset 'apisix/**'
            changeset 'openapi/**'
            changeset 'helm/environments/dev/oan-a2c-gateway.yaml'
          }
        }
      }
      agent { label 'oan-ci-deploy' }
      options { timeout(time: 15, unit: 'MINUTES') }
      steps {
        checkout scm
        sh 'rm -rf built-gateway-chart'
        unstash 'built-gateway-chart'
        withCredentials([file(credentialsId: 'oan-dev-kubeconfig', variable: 'KUBECONFIG')]) {
          sh 'bash ci/deploy-gateway.sh'
        }
      }
    }

    // staging -> Helm release `a2c` on the QA cluster from the promoted archive, then its APISIX routes
    // (every staging build: the first installs them, and the routes chart is repackaged with each one).
    stage('staging → QA cluster (helm)') {
      when { beforeAgent true; branch 'staging' }
      agent { label 'oan-ci-deploy' }   // VPN agent with helm and kubectl; must reach the QA API
      options { timeout(time: 45, unit: 'MINUTES') }
      steps {
        checkout scm
        unstash 'built-chart'
        withCredentials([file(credentialsId: 'oan-qa-kubeconfig', variable: 'KUBECONFIG')]) {
          sh 'DEPLOY_ENV=staging bash ci/deploy-helm-dev.sh'
        }
      }
    }

    stage('staging → QA cluster (apisix)') {
      when { beforeAgent true; branch 'staging' }
      agent { label 'oan-ci-deploy' }
      options { timeout(time: 15, unit: 'MINUTES') }
      steps {
        checkout scm
        sh 'rm -rf built-gateway-chart'
        unstash 'built-gateway-chart'
        withCredentials([file(credentialsId: 'oan-qa-kubeconfig', variable: 'KUBECONFIG')]) {
          sh 'GATEWAY_VALUES=helm/environments/staging/oan-a2c-gateway.yaml bash ci/deploy-gateway.sh'
        }
      }
    }

    // ---------------------- Helm chart publish (same name as the image) ----------------------
    // Adds the archive built by 'Package chart' to repository/develop/ of oan-helm, only after
    // the oan_dev and gateway deploys succeeded.
    stage('Publish chart') {
      when { anyOf { branch 'develop'; branch 'staging' } }
      steps {
        // UNSTABLE, not failed: the image is already deployed.
        catchError(buildResult: 'UNSTABLE', stageResult: 'UNSTABLE') {
          withCredentials([usernamePassword(credentialsId: 'oan-helm-fork-token', usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')]) {
            sh 'python3 ci/package_chart.py publish'
          }
        }
      }
    }

    stage('Publish gateway chart') {
      when {
        beforeAgent true
        anyOf {
          branch 'staging'
          allOf {
            branch 'develop'
            anyOf {
              changeset 'apisix/**'
              changeset 'openapi/**'
              changeset 'helm/environments/dev/oan-a2c-gateway.yaml'
            }
          }
        }
      }
      steps {
        // UNSTABLE, not failed: the routes are already installed.
        catchError(buildResult: 'UNSTABLE', stageResult: 'UNSTABLE') {
          withCredentials([usernamePassword(credentialsId: 'oan-helm-fork-token', usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')]) {
            sh 'python3 ci/package_chart.py gateway-publish'
          }
        }
      }
    }
  }

  post {
    // Bound the BuildKit cache so the shared agent's disk can't fill over many builds.
    // `docker rmi` only drops the final tag; the build cache is a SEPARATE store that
    // otherwise grows unbounded (frappe layers are large). --max-used-space caps it at
    // ~20GB (buildx v0.34+; replaces the deprecated --keep-storage). Scoped to the build
    // cache only — never `docker system prune`, which wipes other jobs on a shared agent.
    always  { sh 'docker buildx prune -f --max-used-space=20GB 2>/dev/null || true' }
    success { echo "OK  ${env.BRANCH_NAME} #${env.BUILD_NUMBER} -> ${env.IMMUTABLE_TAG}" }
    failure { echo "FAIL ${env.BRANCH_NAME} #${env.BUILD_NUMBER}" }
  }
}
