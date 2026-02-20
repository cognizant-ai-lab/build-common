#!/usr/bin/env bash
set -euo pipefail

if [ -n "$INPUT_PYLINT_CMD" ]; then
  echo "Running custom pylint command: ${INPUT_PYLINT_CMD}"
  eval "$INPUT_PYLINT_CMD"
else
  echo "Running pylint on: ${INPUT_SOURCES}"
  # Word splitting is intentional: INPUT_SOURCES is space-separated
  # shellcheck disable=SC2086
  pylint $INPUT_SOURCES
fi
