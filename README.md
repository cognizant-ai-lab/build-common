# build-common

Reusable GitHub Actions building blocks for cognizant-ai-lab repositories.

## Overview

This repository provides shared composite actions, reusable workflows, and scripts that can be used across any repository to reduce duplication and standardize CI/CD practices. The primary consumers today are the most active ns* repositories.

## Documentation

- [Implementation Plan](./IMPLEMENTATION_PLAN.md) - Detailed plan outlining the reusable building blocks to be implemented

## Composite Actions

Available actions live in the `actions/` directory. Each action is a subdirectory
containing an `action.yml` file. This one-to-one relationship between directory
and `action.yml` is a GitHub requirement: the metadata filename must be
`action.yml` (or `action.yaml`), so the enclosing directory name is what
distinguishes one action from another.

See [Metadata syntax for GitHub Actions](https://docs.github.com/en/actions/creating-actions/metadata-syntax-for-github-actions)
for details on this constraint.

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

Copyright 2025-2026 Cognizant Technology Solutions Corp.
