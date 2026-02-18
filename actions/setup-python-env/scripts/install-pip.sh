#!/usr/bin/env bash
set -euo pipefail

if [ -n "$INPUT_PIP_VERSION" ]; then
  echo "Installing pip==${INPUT_PIP_VERSION}"
  python -m pip install "pip==${INPUT_PIP_VERSION}"
else
  echo "Using bundled pip (no version specified)"
fi
echo "pip version: $(pip --version)"
