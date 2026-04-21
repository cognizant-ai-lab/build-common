#!/usr/bin/env bash
set -euo pipefail

echo "Running ruff format check on: ${INPUT_SOURCES}"
# Skip the build-common checkout path when callers pass
# sources like ".".  Use --config so the exclusion is
# additive with the consuming repo's own ruff config rather
# than replacing it (CLI --exclude overrides config).
# Word splitting is intentional: INPUT_SOURCES is space-separated
# shellcheck disable=SC2086
ruff format --check --diff \
  --config "extend-exclude = ['.build-common']" \
  $INPUT_SOURCES
