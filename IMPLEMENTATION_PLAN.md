# Build-Common Repository Plan

## Executive Summary

This document outlines a plan for creating reusable GitHub Actions building blocks in the `build-common` repository. The analysis is based on examining workflows across 9 repositories with active CI/CD pipelines in the cognizant-ai-lab organization.

### Repositories Analyzed

**With Active Workflows (9 repos):**
| Repository | Language | Workflow Files | Key Patterns |
|------------|----------|----------------|--------------|
| neuro-san | Python | 5 | tests, publish, codeql, integration, smoke |
| neuro-san-ui | TypeScript | 4 | orchestrator, test, build, publish |
| neuro-ui | TypeScript | 4 | orchestrator, test, build, deploy |
| neuro-san-studio | Python | 3 | tests, dispatch-to-deploy, integration |
| neuro-san-deploy | Dockerfile | 2 | build-push, test (lint) |
| neuro-san-web-client | Python | 3 | tests, publish, codeql |
| neuro-san-benchmarking | Python | 1 | tests |
| ns-usageboard | TypeScript | 1 | build-push |
| idea-brainstorm-demo | Python | 3 | tests, build, codeql |

**Without Workflows (12 repos):**
neuro-san-1c, neuro-sand, neuro-san-airline, neuro-san-studio-sandbox, neuro-san-dbox, neuro-san-cc, neuro-san-robotics, neuro-san-weforum, neuroai-jupyter-demo, ns-usageboard-api, ns-usagelogger, agentspace_neurosan_adapter

---

## Recommended Structure for build-common

```
build-common/
├── .github/
│   └── workflows/
│       ├── _python-quality-gate.yml      # Reusable workflow
│       ├── _node-quality-gate.yml        # Reusable workflow
│       ├── _docker-build-push.yml        # Reusable workflow
│       ├── _codeql-analysis.yml          # Reusable workflow
│       └── _orchestrator-template.yml    # Reference template
├── actions/
│   ├── setup-python-env/                 # Composite action
│   ├── setup-node-env/                   # Composite action
│   ├── run-python-lint/                  # Composite action
│   ├── run-shellcheck/                   # Composite action
│   ├── run-hadolint/                     # Composite action
│   ├── docker-build-check/               # Composite action
│   ├── aws-ecr-auth/                     # Composite action
│   ├── docker-buildx-push/               # Composite action
│   ├── slack-notify/                     # Composite action
│   ├── compute-version/                  # Composite action
│   ├── rollup-qa-results/                # Composite action
│   └── gitops-update-yaml/               # Composite action
├── scripts/
│   ├── determine_version.sh              # Shared script
│   ├── compute_image_tag.sh              # Shared script
│   ├── deploy_to_cluster.py              # Shared script
│   ├── run_pylint.sh                     # Shared script
│   ├── run_shellcheck.sh                 # Shared script
│   └── run_markdownlint.sh               # Shared script
└── README.md
```

---

## Part 1: Reusable Workflows (workflow_call)

### 1.1 Python Quality Gate Workflow

**File:** `.github/workflows/_python-quality-gate.yml`

**Status:** Implemented

**Purpose:** Standardized Python testing pipeline with selectable lint
toolchain. Supports both the modern ruff stack (used by neuro-san-studio)
and the legacy flake8/black/isort stack (used by neuro-san, nsflow,
idea-brainstorm-demo).

**Current Duplication Found In:**
- neuro-san/workflows/tests.yml
- neuro-san-studio/workflows/tests.yml
- neuro-san-web-client/workflows/tests.yml
- neuro-san-benchmarking/workflows/tests.yml
- idea-brainstorm-demo/workflows/tests.yml

**Key design decisions:**

- `lint-toolchain` selector (`"ruff"` or `"legacy"`) replaces individual
  `run-flake8` / `run-black` / `run-isort` booleans. Prevents invalid
  combinations and gives repos a coherent preset.
- `lint-command-override` escape hatch lets repos with complex Makefile
  orchestration (e.g. `make lint-check`) bypass individual tool steps.
- `pylint-command` override supports repos like neuro-san that use
  custom pylint scripts with plugins and directory exclusions.
- Default toolchain is `ruff` so new repos get the modern stack.
  Existing repos explicitly opt into `legacy` during transition.

**Inputs (summary):**

| Input | Default | Description |
|-------|---------|-------------|
| `lint-toolchain` | `ruff` | `"ruff"` or `"legacy"` |
| `python-version` | `3.12` | Python version for container |
| `sources` | `.` | Directories for ruff/pylint |
| `run-pylint` | `true` | Run pylint |
| `pylint-command` | *(empty)* | Custom pylint invocation |
| `run-black-check` | `false` | black --check (legacy only) |
| `run-isort-check` | `false` | isort --check-only (legacy only) |
| `run-shellcheck` | `true` | Run shellcheck |
| `run-markdownlint` | `false` | Run pymarkdownlint |
| `run-pytest` | `true` | Run pytest |
| `pytest-markers` | `not integration and not smoke` | Marker filter |
| `check-readme-pypi` | `false` | PyPI README render check |
| `enable-slack` | `true` | Slack notifications |
| `lint-command-override` | *(empty)* | Skip lint steps, run this |
| `test-command-override` | *(empty)* | Skip pytest, run this |

See the workflow file for the full input definitions.

**Steps:**
1. Checkout repository
2. Fork detection (skip Slack on forks)
3. Install system packages (shellcheck, make, extras)
4. Install Python dependencies (venv, requirements, build-requirements)
5. Show installed packages (pip freeze)
6. Lint command override OR individual lint steps:
   - **ruff path:** ruff format --check, ruff check
   - **legacy path:** flake8, optional black --check, optional isort
7. Run pylint (optional, supports custom command)
8. Run shellcheck (optional, supports custom command)
9. Run pymarkdownlint (optional, supports custom command)
10. Test command override OR pytest with markers
11. Check README renders on PyPI (optional)
12. Slack notification on success/failure (with fork detection)

**Example usage (ruff, e.g. neuro-san-studio):**
```yaml
jobs:
  test:
    uses: cognizant-ai-lab/build-common/.github/workflows/_python-quality-gate.yml@<sha>
    with:
      lint-toolchain: 'ruff'
      python-version: '3.13'
      sources: 'run.py apps coded_tools tests'
      run-markdownlint: true
    secrets:
      # Pass OPENAI_API_KEY when the repo has tests that
      # depend on OpenAI (e.g. neuro-san, neuro-san-studio).
      # OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

**Example usage (legacy, e.g. neuro-san):**
```yaml
jobs:
  test:
    uses: cognizant-ai-lab/build-common/.github/workflows/_python-quality-gate.yml@<sha>
    with:
      lint-toolchain: 'legacy'
      pylint-command: 'build_scripts/run_pylint.sh'
      shellcheck-command: 'build_scripts/run_shellcheck.sh'
      markdownlint-command: 'build_scripts/run_markdownlint.sh'
      run-markdownlint: true
    secrets:
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

### 1.2 Node.js Quality Gate Workflow

**File:** `.github/workflows/_node-quality-gate.yml`

**Purpose:** Standardized TypeScript/Node.js testing pipeline

**Current Duplication Found In:**
- neuro-san-ui/workflows/test.yml
- neuro-ui/workflows/test.yml

**Note:** These two files are explicitly marked as "copy-pasta" with a Jira ticket (UN-3573) to consolidate them.

**Inputs:**
```yaml
inputs:
  node-version:
    description: 'Node.js version to use'
    required: false
    default: '24'
    type: string
  working-directory:
    description: 'Working directory for the job'
    required: false
    default: '.'
    type: string
  dockerfile-path:
    description: 'Path to Dockerfile for linting'
    required: false
    default: 'Dockerfile'
    type: string
  run-eslint:
    description: 'Run ESLint check'
    required: false
    default: true
    type: boolean
  run-prettier:
    description: 'Run Prettier format check'
    required: false
    default: true
    type: boolean
  run-shellcheck:
    description: 'Run ShellCheck on scripts'
    required: false
    default: true
    type: boolean
  run-hadolint:
    description: 'Run hadolint on Dockerfile'
    required: false
    default: true
    type: boolean
  run-knip:
    description: 'Run knip unused code check'
    required: false
    default: true
    type: boolean
  run-tsc:
    description: 'Run TypeScript compilation'
    required: false
    default: true
    type: boolean
  run-docker-build-check:
    description: 'Run Docker build check'
    required: false
    default: true
    type: boolean
  run-unit-tests:
    description: 'Run unit tests'
    required: false
    default: true
    type: boolean
  generate-command:
    description: 'Command to run for code generation (e.g., yarn generate)'
    required: false
    default: ''
    type: string
  test-command:
    description: 'Command to run tests'
    required: false
    default: 'yarn test'
    type: string
secrets:
  LEAF_APP_PRIVATE_KEY:
    required: false
  GITHUB_TOKEN_NPM_PACKAGE_READ:
    required: false
```

**Steps to Include:**
1. Checkout repository
2. Configure AWS credentials (for secrets if needed)
3. Get GitHub token for NPM packages (if needed)
4. Setup yarn via corepack
5. Setup Node.js with cache
6. Configure .yarnrc.yml for GitHub Packages auth
7. Install dependencies
8. Install prerequisites (shellcheck, protobuf if needed)
9. Run code generation (optional)
10. Run ESLint (continue-on-error)
11. Run ShellCheck (continue-on-error)
12. Run Prettier (continue-on-error)
13. Run knip (continue-on-error)
14. Run hadolint (continue-on-error)
15. Run Docker build check (continue-on-error)
16. Run TypeScript compilation (continue-on-error)
17. Run unit tests (continue-on-error)
18. Roll up QA results and set final job status

---

### 1.3 Docker Build and Push Workflow

**File:** `.github/workflows/_docker-build-push.yml`

**Purpose:** Standardized Docker image build and push to ECR

**Current Duplication Found In:**
- neuro-san-ui/workflows/build.yml
- neuro-ui/workflows/build.yml
- neuro-san-deploy/workflows/build-push.yml
- ns-usageboard/workflows/Build-Push.yml
- idea-brainstorm-demo/workflows/build.yml

**Inputs:**
```yaml
inputs:
  revision:
    description: 'Git ref (tag/branch/SHA) to checkout'
    required: false
    type: string
  dockerfile:
    description: 'Path to Dockerfile'
    required: false
    default: 'Dockerfile'
    type: string
  context:
    description: 'Docker build context'
    required: false
    default: '.'
    type: string
  image-tag:
    description: 'Docker image tag'
    required: true
    type: string
  ecr-registry:
    description: 'ECR registry URL'
    required: true
    type: string
  ecr-repository:
    description: 'ECR repository name'
    required: true
    type: string
  aws-region:
    description: 'AWS region'
    required: false
    default: 'us-west-2'
    type: string
  aws-account-id:
    description: 'AWS account ID (12-digit)'
    required: true
    type: string
  aws-role-name:
    description: 'IAM role name for OIDC authentication'
    required: true
    type: string
  build-args:
    description: 'Docker build arguments'
    required: false
    default: ''
    type: string
  platforms:
    description: 'Target platforms'
    required: false
    default: 'linux/amd64'
    type: string
  use-cache:
    description: 'Use GitHub Actions cache for Docker layers'
    required: false
    default: true
    type: boolean
```

**Steps to Include:**
1. Checkout repository
2. Configure AWS credentials via OIDC
3. Login to Amazon ECR
4. Set up Docker Buildx
5. Build and push Docker image with caching

---

### 1.4 CodeQL Analysis Workflow

**File:** `.github/workflows/_codeql-analysis.yml`

**Purpose:** Standardized CodeQL security scanning

**Current Duplication Found In:**
- neuro-san/workflows/codeql.yml
- neuro-san-web-client/workflows/codeql.yml
- idea-brainstorm-demo/workflows/codeql.yml

**Inputs:**
```yaml
inputs:
  languages:
    description: 'Languages to analyze (comma-separated: python, javascript-typescript)'
    required: false
    default: 'python'
    type: string
  schedule-cron:
    description: 'Cron schedule for analysis'
    required: false
    default: '28 22 * * 1'
    type: string
```

---

### 1.5 Orchestrator Template Workflow

**File:** `.github/workflows/_orchestrator-template.yml`

**Purpose:** Reference template for orchestrating test → build → deploy pipelines

**Current Pattern Found In:**
- neuro-san-ui/workflows/orchestrator.yml
- neuro-ui/workflows/orchestrator.yml

**Key Features:**
- Setup job that determines version and deployment environment
- Conditional build based on branch/release
- Conditional deploy based on environment

---

## Part 2: Composite Actions

### 2.1 setup-python-env

**Purpose:** Setup Python environment with caching

**Current Duplication:** All Python repos have similar dependency installation patterns

**Inputs:** `python-version` (default `3.12`), `requirements-file`
(default `requirements.txt`), `requirements-build-file` (default `''`,
skipped when empty), `working-directory`, `use-cache`, `install-extras`

**Key implementation details:**
- Uses `actions/setup-python@v5` with pip caching
- Dynamic `cache-dependency-path` handles empty `requirements-file`
  or `requirements-build-file` without producing invalid paths
- Each install step passes inputs through `env:` variables
  (shell injection hardening)
- `if:` guard skips requirements install when `requirements-file`
  is set to `''`

---

### 2.2 setup-node-env

**Purpose:** Setup Node.js with yarn via corepack and caching

**Current Duplication:** neuro-san-ui and neuro-ui have identical setup patterns

**Inputs:** `node-version` (default `24`), `working-directory`,
`use-cache`, `use-corepack`, `clean-install`, `registry-url`, `scope`

**Key implementation details:**
- Yarn-only (npm and pnpm support can be added later if needed)
- `cache-dependency-path` hardcoded to `yarn.lock`
- Uses `yarn install --immutable` to ensure the lockfile is not
  modified during CI
- `clean-install` is opt-in (default `false`); when enabled it
  removes `node_modules` and clears the yarn cache before install
- Corepack enable/install runs before `actions/setup-node@v4`

---

### 2.3 run-python-lint

**Status:** Implemented

**Purpose:** Run formatting and linting checks with a selectable toolchain
(ruff or legacy flake8/black/isort), plus optional pylint. This is a
lighter composite action for repos that want lint checks without the full
quality gate workflow.

**Inputs:** `toolchain` (default `ruff`), `sources` (required),
`run-pylint` (default `true`), `pylint-command` (default `''`),
`run-black-check` (default `false`), `run-isort-check` (default `false`)

**Key implementation details:**
- Inline scripts extracted to `scripts/` directory following repo
  conventions
- `toolchain` input selects between ruff and legacy code paths
- Legacy-specific toggles (`run-black-check`, `run-isort-check`) are
  ignored when toolchain is `ruff`
- `pylint-command` override supports custom invocations

---

### 2.4 run-shellcheck

**Purpose:** Run ShellCheck on shell scripts

**Current Duplication:** Multiple repos run shellcheck with similar patterns

```yaml
# actions/run-shellcheck/action.yml
name: 'Run ShellCheck'
description: 'Run ShellCheck on shell scripts'
inputs:
  scan-dir:
    description: 'Directory to scan'
    required: false
    default: '.'
runs:
  using: 'composite'
  steps:
    - name: Run ShellCheck
      uses: ludeeus/action-shellcheck@2.0.0
      with:
        scandir: ${{ inputs.scan-dir }}
```

---

### 2.5 run-hadolint

**Purpose:** Lint Dockerfiles with hadolint

**Current Duplication:** neuro-san-ui, neuro-ui, neuro-san-deploy all use hadolint

```yaml
# actions/run-hadolint/action.yml
name: 'Run Hadolint'
description: 'Lint Dockerfiles with hadolint'
inputs:
  dockerfile:
    description: 'Path to Dockerfile'
    required: false
    default: 'Dockerfile'
  failure-threshold:
    description: 'Failure threshold (error, warning, info, style, ignore, none)'
    required: false
    default: 'info'
runs:
  using: 'composite'
  steps:
    - name: Run hadolint
      uses: hadolint/hadolint-action@v3.1.0
      with:
        dockerfile: ${{ inputs.dockerfile }}
        failure-threshold: ${{ inputs.failure-threshold }}
```

---

### 2.6 docker-build-check

**Purpose:** Verify Dockerfile builds without pushing

**Current Duplication:** neuro-san-ui and neuro-ui both do this check

```yaml
# actions/docker-build-check/action.yml
name: 'Docker Build Check'
description: 'Verify Dockerfile builds without pushing'
inputs:
  dockerfile:
    description: 'Path to Dockerfile'
    required: false
    default: 'Dockerfile'
  context:
    description: 'Build context'
    required: false
    default: '.'
runs:
  using: 'composite'
  steps:
    - name: Docker build check
      shell: bash
      run: |
        docker build --check --file ${{ inputs.dockerfile }} ${{ inputs.context }} --quiet > /dev/null
```

---

### 2.7 aws-ecr-auth

**Purpose:** Configure AWS credentials and login to ECR

**Current Duplication:** All repos that push to ECR have similar auth patterns

**Inputs:** `aws-account-id` (required, 12-digit), `aws-role-name`
(required), `aws-region` (default `us-west-2`), `role-session-name`,
`role-duration-seconds`

**Outputs:** `registry` (ECR registry URL)

**Key implementation details:**
- Accepts `aws-account-id` and `aws-role-name` separately to match
  the existing `${{ vars.AWS_ACCOUNT_ID }}` / `${{ vars.AWS_ROLE_NAME }}`
  pattern configured across repos
- Constructs the ARN internally as
  `arn:aws:iam::<account-id>:role/<role-name>`
- Validates account ID is 12 digits and role name is non-empty
- Uses `aws-actions/configure-aws-credentials@v4` and
  `aws-actions/amazon-ecr-login@v2`

---

### 2.8 docker-buildx-push

**Purpose:** Build and push Docker image with buildx and caching

**Current Duplication:** Multiple repos use docker/build-push-action with similar configs

**Inputs:** `context`, `dockerfile`, `tags` (required), `build-args`,
`platforms`, `push`, `use-cache`, `cache-scope`, `provenance`, `sbom`,
`secrets`, `target`, `quiet`

**Outputs:** `digest`, `imageid`, `metadata`

**Key implementation details:**
- Uses `docker/setup-buildx-action@v3` and `docker/build-push-action@v6`
- Cache settings are computed in a separate step to support optional
  `cache-scope` (useful for matrix builds)
- `BUILDKIT_PROGRESS` is configurable via the `quiet` input
- All cache-related values passed through `env:` variables

---

### 2.9 slack-notify

**Purpose:** Send Slack notifications with fork detection

**Current Duplication:** All repos have similar Slack notification patterns

**Inputs:** `status` (required), `message`, `webhook-url` (optional,
skips gracefully when empty), `skip-on-fork`, `mention-on-failure`

**Key implementation details:**
- `webhook-url` is optional with default `''`; when empty the
  notification steps are skipped entirely, preventing CI failures
  on fork PRs where secrets are unavailable
- Payload is built with `jq --null-input` using `--arg` for each
  field, ensuring proper JSON escaping
- Includes a clickable link to the GitHub Actions build run in the
  message body
- All dynamic values passed through `env:` variables (shell injection
  hardening)
- Uses `slackapi/slack-github-action@v2.0.0` with `webhook-type:
  incoming-webhook`

---

### 2.10 compute-version

**Purpose:** Compute version/image tag from git state

**Current Duplication:** Multiple repos have version computation logic

```yaml
# actions/compute-version/action.yml
name: 'Compute Version'
description: 'Compute version/image tag from git state'
inputs:
  mode:
    description: 'Version mode: semver-release, short-sha, pr-version'
    required: false
    default: 'short-sha'
  prefix:
    description: 'Version prefix'
    required: false
    default: ''
  base-version:
    description: 'Base version for pr-version mode'
    required: false
    default: ''
outputs:
  version:
    description: 'Computed version'
    value: ${{ steps.compute.outputs.version }}
  short-sha:
    description: 'Short SHA'
    value: ${{ steps.compute.outputs.short_sha }}
runs:
  using: 'composite'
  steps:
    - name: Compute version
      id: compute
      shell: bash
      run: |
        SHORT_SHA=$(git rev-parse --short=7 HEAD)
        echo "short_sha=$SHORT_SHA" >> $GITHUB_OUTPUT
        
        case "${{ inputs.mode }}" in
          semver-release)
            if [ "${{ github.event_name }}" = "release" ]; then
              VERSION="${{ github.event.release.tag_name }}"
              VERSION="${VERSION#v}"
            else
              VERSION="$SHORT_SHA"
            fi
            ;;
          pr-version)
            BASE="${{ inputs.base-version }}"
            VERSION="${BASE%%-*}-pr.${SHORT_SHA}.${{ github.run_number }}"
            ;;
          short-sha|*)
            VERSION="${{ inputs.prefix }}${SHORT_SHA}"
            ;;
        esac
        
        echo "version=$VERSION" >> $GITHUB_OUTPUT
```

---

### 2.11 rollup-qa-results

**Purpose:** Roll up QA step outcomes and set final job status

**Current Duplication:** neuro-san-ui and neuro-ui have identical rollup logic

```yaml
# actions/rollup-qa-results/action.yml
name: 'Rollup QA Results'
description: 'Roll up QA step outcomes and set final job status'
inputs:
  steps-json:
    description: 'JSON object mapping step IDs to their outcomes'
    required: true
runs:
  using: 'composite'
  steps:
    - name: Roll up QA results
      shell: bash
      run: |
        failures=()
        echo "### Quality and Test Results" >> "$GITHUB_STEP_SUMMARY"
        
        echo '${{ inputs.steps-json }}' | jq -r 'to_entries[] | "\(.key):\(.value)"' | while read line; do
          step_id=$(echo "$line" | cut -d: -f1)
          status=$(echo "$line" | cut -d: -f2)
          
          if [ "$status" = "failure" ] || [ "$status" = "cancelled" ]; then
            failures+=("$step_id")
          fi
          echo "- ${step_id}: ${status}" >> "$GITHUB_STEP_SUMMARY"
        done
        
        if [ ${#failures[@]} -gt 0 ]; then
          echo "Failures detected: ${failures[*]}" >> "$GITHUB_STEP_SUMMARY"
          exit 1
        fi
```

---

### 2.12 gitops-update-yaml

**Purpose:** Update YAML files for GitOps deployments

**Current Duplication:** neuro-ui, neuro-san-deploy, ns-usageboard all update YAML files

```yaml
# actions/gitops-update-yaml/action.yml
name: 'GitOps Update YAML'
description: 'Update YAML files and commit for GitOps deployments'
inputs:
  file-path:
    description: 'Path to YAML file to update'
    required: true
  updates:
    description: 'JSON object of key-value pairs to update (e.g., {"image.tag": "v1.0.0"})'
    required: true
  commit-message:
    description: 'Commit message'
    required: true
  git-user-name:
    description: 'Git user name for commit'
    required: false
    default: 'GitHub Actions'
  git-user-email:
    description: 'Git user email for commit'
    required: false
    default: 'actions@github.com'
  push:
    description: 'Push changes to remote'
    required: false
    default: 'true'
runs:
  using: 'composite'
  steps:
    - name: Update YAML and commit
      shell: bash
      run: |
        # Update YAML file using yq or sed
        echo '${{ inputs.updates }}' | jq -r 'to_entries[] | "\(.key)=\(.value)"' | while read line; do
          key=$(echo "$line" | cut -d= -f1)
          value=$(echo "$line" | cut -d= -f2-)
          # Use yq if available, otherwise sed
          if command -v yq &> /dev/null; then
            yq -i ".$key = \"$value\"" "${{ inputs.file-path }}"
          else
            sed -i "s|$key:.*|$key: \"$value\"|" "${{ inputs.file-path }}"
          fi
        done
        
        git config user.name "${{ inputs.git-user-name }}"
        git config user.email "${{ inputs.git-user-email }}"
        git add "${{ inputs.file-path }}"
        git diff --staged --quiet || git commit -m "${{ inputs.commit-message }}"
        
        if [ "${{ inputs.push }}" = "true" ]; then
          git push
        fi
```

---

## Part 3: Shared Scripts

### 3.1 determine_version.sh

**Purpose:** Determine version and deployment environment based on git event

**Current Location:** neuro-san-ui, neuro-ui (build_scripts/determine_version.sh)

**Functionality:**
- Parse event name (push, release, workflow_dispatch)
- Determine version from release tag or SHA
- Determine deployment environment (dev, staging, prod)
- Set should_build and should_deploy flags

---

### 3.2 compute_image_tag.sh

**Purpose:** Compute Docker image tag from git state

**Current Location:** neuro-san-deploy (.github/scripts/compute_image_tag.sh)

**Functionality:**
- Support override via IMAGE_TAG_OVERRIDE
- Extract version from git tags
- Fall back to short SHA
- Support prefix and unique slug for test builds

---

### 3.3 deploy_to_cluster.py

**Purpose:** Update Helm values files with new image tags

**Current Location:** neuro-san-deploy (.github/scripts/deploy_to_cluster.py)

**Functionality:**
- Parse YAML files
- Update specific keys with proper quoting
- Support dry-run mode
- Handle multiple image tags (neuro-san-studio, ui, usage-api)

---

### 3.4 Linting Scripts

**Purpose:** Standardized linting scripts

**Current Location:** Multiple repos (build_scripts/)

**Scripts to Include:**
- `run_pylint.sh` - Run pylint with standard configuration
- `run_shellcheck.sh` - Run shellcheck on shell scripts
- `run_markdownlint.sh` - Run pymarkdownlint on markdown files
- `run_eslint.sh` - Run ESLint with standard configuration

---

## Part 4: Implementation Priority

### Phase 1: High-Impact Composite Actions (Week 1-2)

1. **slack-notify** - Used by all repos, includes fork detection
2. **aws-ecr-auth** - Used by all repos pushing to ECR
3. **docker-buildx-push** - Standardizes Docker builds
4. **setup-python-env** - Used by 5+ Python repos
5. **setup-node-env** - Used by 3+ Node.js repos

### Phase 2: Reusable Workflows (Week 3-4)

1. **_python-quality-gate.yml** - Consolidates 5 similar test workflows
2. **_node-quality-gate.yml** - Consolidates 2 identical test workflows (addresses UN-3573)
3. **_docker-build-push.yml** - Standardizes ECR builds

### Phase 3: Additional Actions and Scripts (Week 5-6)

1. **compute-version** - Standardizes version computation
2. **rollup-qa-results** - Standardizes QA result aggregation
3. **gitops-update-yaml** - Standardizes GitOps updates
4. **Shared scripts** - Move common scripts to build-common

### Phase 4: CodeQL and Templates (Week 7-8)

1. **_codeql-analysis.yml** - Standardizes security scanning
2. **_orchestrator-template.yml** - Reference implementation
3. Documentation and migration guides

---

## Part 5: Migration Strategy

### For Each Repo:

1. **Add build-common as a dependency** (if using scripts) or reference workflows directly
2. **Replace inline steps** with composite action calls
3. **Replace full workflows** with reusable workflow calls
4. **Test thoroughly** before merging
5. **Update documentation** to reference build-common

### Example Migration (neuro-san tests.yml):

**Before:**
```yaml
- name: Notify Slack on success
  if: success()
  uses: slackapi/slack-github-action@v1.24.0
  with:
    payload: |
      {
        "text": "✅ *Tests Passed* for `${{ github.repository }}` on `${{ github.ref_name }}`"
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

**After:**
```yaml
- name: Notify Slack
  if: always()
  uses: cognizant-ai-lab/build-common/actions/slack-notify@v1
  with:
    status: ${{ job.status }}
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

## Part 6: Design Principles

1. **Fork-Safe**: All actions should gracefully handle fork PRs (skip secret-dependent steps)
2. **Secrets as Inputs**: Never fetch secrets from inside actions; require callers to provide them
3. **Sensible Defaults**: Provide defaults that work for most repos
4. **Opt-In Features**: Use boolean inputs to enable/disable optional features
5. **Version Pinning**: Pin third-party action versions for reproducibility
6. **Backward Compatible**: Design for easy adoption without breaking existing workflows
7. **Well-Documented**: Include clear documentation and examples for each action/workflow

---

## Appendix: Workflow Inventory

### Python Repos - Common Patterns

| Pattern | neuro-san | neuro-san-studio | neuro-san-web-client | neuro-san-benchmarking | idea-brainstorm-demo |
|---------|-----------|------------------|----------------------|------------------------|----------------------|
| Python container | 3.12-slim | 3.13-slim | 3.12-slim | 3.12-slim | 3.12-slim |
| lint toolchain | legacy (flake8) | **ruff** | — | legacy (flake8) | legacy (flake8) |
| pylint | Yes | Yes (make) | No | Yes | Yes |
| shellcheck | Yes | Yes | No | Yes | Yes |
| markdownlint | Yes | Yes (make) | No | Yes | Yes |
| pytest | Yes | Yes | No | Yes | Yes |
| README check | Yes | Yes | Yes | Yes | Yes |
| Slack notify | Yes | Yes | Yes | Yes | No (commented) |
| PyPI publish | Yes | No | Yes | No | No |
| CodeQL | Yes | No | Yes | No | Yes |

### TypeScript Repos - Common Patterns

| Pattern | neuro-san-ui | neuro-ui | ns-usageboard |
|---------|--------------|----------|---------------|
| Node version | 24 | 24 | N/A |
| Yarn corepack | Yes | Yes | N/A |
| ESLint | Yes | Yes | N/A |
| Prettier | Yes | Yes | N/A |
| ShellCheck | Yes | Yes | N/A |
| hadolint | Yes | Yes | N/A |
| knip | Yes | Yes | N/A |
| TypeScript | Yes | Yes | N/A |
| Jest | Yes | Yes | N/A |
| Docker check | Yes | Yes | N/A |
| Rollup QA | Yes | Yes | N/A |
| ECR push | Yes | Yes | Yes |
| Orchestrator | Yes | Yes | No |

---

## Conclusion

The build-common repository provides reusable building blocks that eliminate the significant duplication currently present across cognizant-ai-lab repositories. While the primary consumers today are the most active ns* repositories, the actions and workflows are designed to be reusable by any repository. The highest-impact items are the composite actions for common steps (Slack notifications, AWS/ECR auth, Docker builds) and the reusable workflows for Python and Node.js quality gates.

By implementing this plan, teams will benefit from:
- Reduced maintenance burden (fix once, apply everywhere)
- Consistent CI/CD practices across all repos
- Easier onboarding for new repos
- Centralized security updates for third-party actions
- Standardized deployment patterns
