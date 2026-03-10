#!/usr/bin/env bash
set -euo pipefail

echo "Running ruff format check on: ${INPUT_SOURCES}"
# Word splitting is intentional: INPUT_SOURCES is space-separated
# shellcheck disable=SC2086
ruff format --check --diff $INPUT_SOURCES
