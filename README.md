# build-common

Reusable GitHub Actions building blocks for cognizant-ai-lab repositories.

## Overview

This repository provides shared composite actions, reusable workflows, and scripts that can be used across the neuro* and ns* repositories to reduce duplication and standardize CI/CD practices.

## Documentation

- [Implementation Plan](./IMPLEMENTATION_PLAN.md) - Detailed plan outlining the reusable building blocks to be implemented

## Structure

```
build-common/
├── .github/
│   └── workflows/           # Reusable workflows (workflow_call)
├── actions/                 # Composite actions
│   ├── slack-notify/        # Slack notifications with fork detection
│   ├── aws-ecr-auth/        # AWS OIDC + ECR authentication
│   ├── docker-buildx-push/  # Docker build and push with caching
│   ├── setup-python-env/    # Python environment setup
│   └── setup-node-env/      # Node.js environment setup
├── scripts/                 # Shared shell/python scripts
└── README.md
```

## Available Actions

### slack-notify

Send Slack notifications with automatic fork detection to skip notifications on fork PRs.

```yaml
- name: Notify Slack
  if: always()
  uses: cognizant-ai-lab/build-common/actions/slack-notify@main
  with:
    status: ${{ job.status }}
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    # Optional inputs:
    message: 'Tests completed'           # Custom message
    skip-on-fork: 'true'                 # Skip for fork PRs (default: true)
    mention-on-failure: 'true'           # @channel on failure
```

### aws-ecr-auth

Configure AWS credentials via OIDC and login to Amazon ECR.
The ARN is constructed from `aws-account-id` and `aws-role-name`
to match existing repo-level variable conventions.

```yaml
- name: Authenticate to AWS and ECR
  id: ecr-auth
  uses: cognizant-ai-lab/build-common/actions/aws-ecr-auth@main
  with:
    aws-account-id: ${{ vars.AWS_ACCOUNT_ID }}
    aws-role-name: ${{ vars.AWS_ROLE_NAME }}
    aws-region: us-west-2  # Optional, defaults to us-west-2

# Use the registry output
- name: Build image
  run: |
    docker build -t ${{ steps.ecr-auth.outputs.registry }}/my-repo:latest .
```

### docker-buildx-push

Build and push Docker images using buildx with GitHub Actions cache support.

```yaml
- name: Build and push Docker image
  uses: cognizant-ai-lab/build-common/actions/docker-buildx-push@main
  with:
    tags: |
      ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ env.VERSION }}
      ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:latest
    # Optional inputs:
    context: '.'
    dockerfile: 'Dockerfile'
    build-args: |
      NODE_VERSION=22
      BUILD_DATE=${{ github.event.head_commit.timestamp }}
    platforms: 'linux/amd64'
    use-cache: 'true'
    push: 'true'
```

### setup-python-env

Setup Python environment with dependencies and pip caching.

```yaml
- name: Setup Python
  uses: cognizant-ai-lab/build-common/actions/setup-python-env@main
  with:
    python-version: '3.12'
    requirements-file: 'requirements.txt'
    requirements-build-file: 'requirements-build.txt'  # Optional
    # Optional inputs:
    working-directory: '.'
    use-cache: 'true'
    install-extras: 'pytest pytest-cov'  # Additional packages
```

### setup-node-env

Setup Node.js environment with yarn via corepack and caching.
Only yarn is supported at this time; npm and pnpm support can
be added later if needed.

```yaml
- name: Setup Node.js
  uses: cognizant-ai-lab/build-common/actions/setup-node-env@main
  with:
    node-version: '22'
    # Optional inputs:
    working-directory: '.'
    use-cache: 'true'
    use-corepack: 'true'     # Enable corepack for version management
    clean-install: 'false'   # Clean node_modules before install
    registry-url: ''         # For private packages
```

## Reusable Workflows

Coming in Phase 2:
- `_python-quality-gate.yml` - Python testing pipeline (pylint, flake8, pytest)
- `_node-quality-gate.yml` - Node.js testing pipeline (ESLint, Jest, TypeScript)
- `_docker-build-push.yml` - Docker build and ECR push workflow
- `_codeql-analysis.yml` - CodeQL security scanning

## Migration Guide

To migrate from inline workflow steps to these actions:

### Before (inline Slack notification):
```yaml
- name: Notify Slack on success
  if: success()
  uses: slackapi/slack-github-action@v1.24.0
  with:
    payload: |
      {
        "text": "Tests Passed for ${{ github.repository }}"
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### After (using build-common):
```yaml
- name: Notify Slack
  if: always()
  uses: cognizant-ai-lab/build-common/actions/slack-notify@main
  with:
    status: ${{ job.status }}
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Versioning

Use `@main` for the latest version, or pin to a specific tag (e.g., `@v1.0.0`) for stability.

## License

Copyright 2025 Cognizant Technology Solutions Corp.
