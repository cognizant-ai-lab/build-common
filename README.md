# build-common

Reusable GitHub Actions building blocks for cognizant-ai-lab repositories.

## Overview

This repository provides shared composite actions, reusable workflows, and scripts that can be used across repositories to reduce duplication and standardize CI/CD practices.

## Documentation

- [Implementation Plan](./IMPLEMENTATION_PLAN.md) - Detailed plan outlining the reusable building blocks to be implemented

## Structure (Planned)

```
build-common/
├── .github/
│   └── workflows/           # Reusable workflows (workflow_call)
├── actions/                 # Composite actions
├── scripts/                 # Shared shell/python scripts
└── README.md
```

## Usage

Once implemented, repos can reference actions and workflows from this repository:

```yaml
# Using a composite action
- uses: cognizant-ai-lab/build-common/actions/slack-notify@v1
  with:
    status: ${{ job.status }}
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}

# Using a reusable workflow
jobs:
  test:
    uses: cognizant-ai-lab/build-common/.github/workflows/_python-quality-gate.yml@v1
    with:
      python-version: '3.12'
    secrets:
      SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## License

Copyright 2025 Cognizant Technology Solutions Corp.

## Status

This repository is under active development.
