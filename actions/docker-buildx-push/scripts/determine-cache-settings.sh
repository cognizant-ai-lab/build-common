#!/usr/bin/env bash
set -euo pipefail

if [ "$INPUT_USE_CACHE" = "true" ]; then
  if [ -n "$INPUT_CACHE_SCOPE" ]; then
    FROM="type=gha,scope=${INPUT_CACHE_SCOPE}"
    TO="type=gha,mode=max,scope=${INPUT_CACHE_SCOPE}"
    echo "cache-from=${FROM}" >> "$GITHUB_OUTPUT"
    echo "cache-to=${TO}" >> "$GITHUB_OUTPUT"
  else
    echo "cache-from=type=gha" >> "$GITHUB_OUTPUT"
    echo "cache-to=type=gha,mode=max" >> "$GITHUB_OUTPUT"
  fi
else
  echo "cache-from=" >> "$GITHUB_OUTPUT"
  echo "cache-to=" >> "$GITHUB_OUTPUT"
fi
