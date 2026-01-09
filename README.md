# build-common

Reusable GitHub Actions building blocks for cognizant-ai-lab repositories.

## Overview

This repository provides shared composite actions, reusable workflows, and scripts that can be used across repositories to reduce duplication and standardize CI/CD practices.

## Documentation

- [Implementation Plan](./IMPLEMENTATION_PLAN.md) - Detailed plan outlining the reusable building blocks to be implemented

## Structure

```
build-common/
├── .github/
│   └── workflows/           # Reusable workflows (workflow_call)
│       ├── _python-quality-gate.yml
│       ├── _node-quality-gate.yml
│       ├── _docker-build-push.yml
│       └── _codeql-analysis.yml
├── actions/                 # Composite actions
│   ├── slack-notify/
│   ├── aws-ecr-auth/
│   ├── docker-buildx-push/
│   ├── setup-python-env/
│   └── setup-node-env/
├── scripts/                 # Shared shell/python scripts
└── README.md
```

## Reusable Workflows

### Python Quality Gate

Complete Python CI pipeline with linting and testing.

```yaml
name: CI
on: [push, pull_request]

jobs:
  quality-gate:
    uses: cognizant-ai-lab/build-common/.github/workflows/_python-quality-gate.yml@main
    with:
      python-version: '3.12'
      source-directory: 'src'
      run-pylint: true
      run-flake8: true
      run-pytest: true
    secrets:
      SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Node.js Quality Gate

Complete Node.js CI pipeline with linting, type checking, and testing.

```yaml
name: CI
on: [push, pull_request]

jobs:
  quality-gate:
    uses: cognizant-ai-lab/build-common/.github/workflows/_node-quality-gate.yml@main
    with:
      node-version: '22'
      package-manager: 'yarn'
      run-lint: true
      run-format-check: true
      run-typecheck: true
      run-test: true
    secrets:
      SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Docker Build and Push

Build and push Docker images to ECR with OIDC authentication.

```yaml
name: Build and Push
on:
  push:
    branches: [main]

jobs:
  build:
    uses: cognizant-ai-lab/build-common/.github/workflows/_docker-build-push.yml@main
    with:
      image-name: my-service
      tag: ${{ github.sha }}
      additional-tags: |
        latest
        ${{ github.ref_name }}
    secrets:
      AWS_ROLE_ARN: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/${{ vars.AWS_ROLE_NAME }}
      SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### CodeQL Analysis

Security scanning with GitHub CodeQL.

```yaml
name: CodeQL
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'

jobs:
  analyze:
    uses: cognizant-ai-lab/build-common/.github/workflows/_codeql-analysis.yml@main
    with:
      languages: 'javascript,python'
      queries: 'security-extended'
    secrets:
      SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Composite Actions

### slack-notify

Send Slack notifications with fork detection.

```yaml
- uses: cognizant-ai-lab/build-common/actions/slack-notify@main
  with:
    status: ${{ job.status }}
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    mention-on-failure: 'true'
```

### aws-ecr-auth

AWS OIDC authentication and ECR login.

```yaml
- id: ecr-auth
  uses: cognizant-ai-lab/build-common/actions/aws-ecr-auth@main
  with:
    aws-role-arn: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/${{ vars.AWS_ROLE_NAME }}
    aws-region: us-west-2
```

### docker-buildx-push

Docker build and push with caching.

```yaml
- uses: cognizant-ai-lab/build-common/actions/docker-buildx-push@main
  with:
    tags: ${{ steps.ecr-auth.outputs.registry }}/my-repo:latest
    build-args: |
      NODE_VERSION=22
```

### setup-python-env

Python environment setup with caching.

```yaml
- uses: cognizant-ai-lab/build-common/actions/setup-python-env@main
  with:
    python-version: '3.12'
    requirements-file: 'requirements.txt'
```

### setup-node-env

Node.js environment setup with corepack.

```yaml
- uses: cognizant-ai-lab/build-common/actions/setup-node-env@main
  with:
    node-version: '22'
    package-manager: 'yarn'
```

## Versioning

Use `@main` for the latest version, or pin to a specific tag (e.g., `@v1.0.0`) for stability.

## License

Copyright 2025 Cognizant Technology Solutions Corp.
