#!/usr/bin/env bash
set -euo pipefail

if [ "$GH_EVENT" = "pull_request" ]; then
  if [ "$GH_HEAD_REPO" != "$GH_SELF_REPO" ]; then
    echo "is_fork=true" >> "$GITHUB_OUTPUT"
    echo "Detected fork PR - will be skipped"
  else
    echo "is_fork=false" >> "$GITHUB_OUTPUT"
  fi
else
  echo "is_fork=false" >> "$GITHUB_OUTPUT"
fi
