#!/usr/bin/env bash
set -euo pipefail

if [ -f "$INPUT_REQUIREMENTS_FILE" ]; then
  echo "Installing from ${INPUT_REQUIREMENTS_FILE}"
  pip install --requirement "$INPUT_REQUIREMENTS_FILE"
else
  echo "::error::Required file ${INPUT_REQUIREMENTS_FILE} not found"
  exit 1
fi
