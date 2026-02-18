#!/usr/bin/env bash
set -euo pipefail

corepack enable
if [ -f "package.json" ]; then
  corepack install
  echo "Yarn version: $(yarn --version)"
fi
