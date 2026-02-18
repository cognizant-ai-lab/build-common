#!/usr/bin/env bash
set -euo pipefail

ACCT_PATTERN='^[0-9]{12}$'
if [[ ! "$INPUT_ACCOUNT_ID" =~ $ACCT_PATTERN ]]; then
  echo "::error::Invalid aws-account-id (expected 12 digits)"
  exit 1
fi
if [ -z "$INPUT_ROLE_NAME" ]; then
  echo "::error::aws-role-name must not be empty"
  exit 1
fi
ARN="arn:aws:iam::${INPUT_ACCOUNT_ID}"
ARN="${ARN}:role/${INPUT_ROLE_NAME}"
echo "role-arn=${ARN}" >> "$GITHUB_OUTPUT"
