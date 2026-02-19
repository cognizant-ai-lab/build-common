#!/usr/bin/env bash
set -euo pipefail

if [ -z "$INPUT_BASE_URI" ]; then
  echo "::error::base-uri must not be empty"
  exit 1
fi
if [ -z "$INPUT_TENANT" ]; then
  echo "::error::cx-tenant must not be empty"
  exit 1
fi
if [ -z "$INPUT_CLIENT_ID" ]; then
  echo "::error::cx-client-id must not be empty"
  exit 1
fi
if [ -z "$INPUT_CLIENT_SECRET" ]; then
  echo "::error::cx-client-secret must not be empty"
  exit 1
fi

echo "Checkmarx One inputs validated successfully"
