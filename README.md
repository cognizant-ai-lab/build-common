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

### Publishing to PyPI

The `build-python-dists` action builds a wheel and sdist into `dist/`. The
upload step is deliberately *not* part of it: `pypa/gh-action-pypi-publish`
must be called directly from the consumer's own publish workflow, because

- it wraps a Docker action, and when nested inside a composite action the
  `github.action_*` context resolves to the calling action's repository
  (actions/runner#2473), so it tries to pull a nonexistent
  `ghcr.io/<caller-repo>:<sha>` image; and
- PyPI Trusted Publishing matches the OIDC `job_workflow_ref` claim, and
  [reusable workflows are not supported](https://docs.pypi.org/trusted-publishers/troubleshooting/)
  (pypi/warehouse#11096), so a shared reusable workflow cannot authenticate
  either.

Keep the caller job's `pypi` environment and `id-token: write` permission in
place, and pin the publish action to the SHA recorded in
[actions-manifest.yml](./actions-manifest.yml):

```yaml
- name: Build distributions
  uses: cognizant-ai-lab/build-common/actions/build-python-dists@<release-sha>
  with:
    python-version: '3.10'

# v1.14.0
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b
```

Pip caching is opt-in and requires a dependency file:

```yaml
- name: Build distributions
  uses: cognizant-ai-lab/build-common/actions/build-python-dists@<release-sha>
  with:
    use-cache: 'true'
    cache-dependency-path: requirements.txt
```

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
