#!/usr/bin/env bash
# check-actions-manifest.sh
#
# Validates that actions-manifest.yml is complete and
# consistent with the workflow and composite-action files.
#
# Checks performed:
#   1. Every SHA in the manifest matches the actual files.
#   2. Every third-party "uses:" reference in repo YAML
#      files appears in the manifest (no untracked actions).
#
# Usage:
#   scripts/check-actions-manifest.sh          # from repo root
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="${REPO_ROOT}/actions-manifest.yml"
ERRORS=0

if [ ! -f "$MANIFEST" ]; then
  echo "ERROR: Manifest not found at ${MANIFEST}" >&2
  exit 1
fi

# ── Requires: python3 + PyYAML ──────────────────────────
if ! python3 -c "import yaml" 2>/dev/null; then
  echo "ERROR: PyYAML is required. Install with: pip install pyyaml" >&2
  exit 1
fi

echo "=== Check 1: Manifest SHAs match workflow files ==="

RECORDS=$(python3 -c "
import yaml, sys
with open('${MANIFEST}') as f:
    data = yaml.safe_load(f)
for entry in data['actions']:
    for path in entry['used_in']:
        print('{}\t{}\t{}\t{}'.format(
            entry['action'], entry['sha'],
            entry['version'], path))
")

while IFS=$'\t' read -r action sha version filepath; do
  target="${REPO_ROOT}/${filepath}"
  if [ ! -f "$target" ]; then
    echo "  FAIL: ${filepath} listed in manifest but file not found"
    ERRORS=$((ERRORS + 1))
    continue
  fi

  # Deduplicate: an action may appear more than once in a
  # file (e.g. checkout used twice).  All occurrences must
  # share the same SHA — collect unique values.
  current_shas=$(grep -oP "uses:\s+${action}@\K[0-9a-f]+" \
                 "$target" 2>/dev/null | sort -u || true)

  if [ -z "$current_shas" ]; then
    echo "  FAIL: ${action} not found in ${filepath}"
    ERRORS=$((ERRORS + 1))
    continue
  fi

  sha_count=$(echo "$current_shas" | wc -l)
  if [ "$sha_count" -gt 1 ]; then
    echo "  FAIL: ${filepath}: ${action} has mixed SHAs:"
    echo "${current_shas//$'\n'/$'\n'        }" | sed '1s/^/        /'
    ERRORS=$((ERRORS + 1))
    continue
  fi

  if [ "$current_shas" != "$sha" ]; then
    echo "  FAIL: ${filepath}: ${action}"
    echo "        manifest: ${sha} (${version})"
    echo "        actual:   ${current_shas}"
    ERRORS=$((ERRORS + 1))
  else
    echo "  OK:   ${filepath}: ${action}@${version}"
  fi
done <<< "$RECORDS"

echo ""
echo "=== Check 2: All actions in repo are in the manifest ==="

# Build a set of manifested actions (owner/repo format)
MANIFESTED=$(python3 -c "
import yaml
with open('${MANIFEST}') as f:
    data = yaml.safe_load(f)
for entry in data['actions']:
    print(entry['action'])
" | sort -u)

# Scan all YAML files for third-party uses: references.
# Exclude:
#   - Local path references (uses: ./ or uses: .build-common)
#   - GitHub-owned runner actions that are part of composite
#     action internals (actions/runner/*)
# Pattern: uses: <owner>/<repo>@<sha-or-tag>
YAML_FILES=$(find "${REPO_ROOT}/.github/workflows" \
                  "${REPO_ROOT}/actions" \
             -name '*.yml' -o -name '*.yaml' 2>/dev/null)

for yaml_file in $YAML_FILES; do
  rel_path="${yaml_file#"${REPO_ROOT}/"}"

  # Extract all uses: references that look like owner/repo@ref
  refs=$(grep -oP 'uses:\s+\K[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?=@)' \
         "$yaml_file" 2>/dev/null | sort -u || true)

  for ref in $refs; do
    if echo "$MANIFESTED" | grep -qxF "$ref"; then
      continue
    fi
    echo "  FAIL: ${rel_path} uses ${ref} which is NOT in the manifest"
    ERRORS=$((ERRORS + 1))
  done
done

echo ""
if [ "$ERRORS" -gt 0 ]; then
  echo "FAILED: ${ERRORS} issue(s) found."
  echo "Run 'scripts/sync-actions-manifest.sh' to fix SHA drift,"
  echo "or add missing actions to actions-manifest.yml."
  exit 1
else
  echo "PASSED: Manifest is complete and consistent."
fi
