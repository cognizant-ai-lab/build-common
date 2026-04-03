#!/usr/bin/env bash
# sync-actions-manifest.sh
#
# Reads ACTIONS_MANIFEST.yaml and patches every workflow /
# composite-action file so that pinned SHAs and version
# comments match the manifest.
#
# Usage:
#   scripts/sync-actions-manifest.sh            # from repo root
#   scripts/sync-actions-manifest.sh --check    # exit 1 on drift
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="${REPO_ROOT}/ACTIONS_MANIFEST.yaml"
CHECK_ONLY=false

if [ "${1:-}" = "--check" ]; then
  CHECK_ONLY=true
fi

if [ ! -f "$MANIFEST" ]; then
  echo "ERROR: Manifest not found at ${MANIFEST}" >&2
  exit 1
fi

# ── Requires: python3 + PyYAML ──────────────────────────
if ! python3 -c "import yaml" 2>/dev/null; then
  echo "ERROR: PyYAML is required. Install with: pip install pyyaml" >&2
  exit 1
fi

DRIFT=0

# Parse the manifest and emit tab-separated records:
#   action \t sha \t version \t file
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
    echo "WARN: ${filepath} listed in manifest but not found" >&2
    continue
  fi

  # An action may appear more than once in the same file
  # (e.g. checkout used for two different repos).  Collect
  # the unique SHAs currently present.
  current_shas=$(grep -oP "uses:\s+${action}@\K[0-9a-f]+" \
                 "$target" 2>/dev/null | sort -u || true)

  if [ -z "$current_shas" ]; then
    echo "WARN: ${action} not found in ${filepath}" >&2
    continue
  fi

  # If every occurrence already matches, nothing to do.
  if [ "$current_shas" = "$sha" ]; then
    continue
  fi

  echo "DRIFT: ${filepath}: ${action} -> @${sha} (${version})"
  DRIFT=1

  if [ "$CHECK_ONLY" = true ]; then
    continue
  fi

  # Replace every stale SHA for this action in one pass.
  while IFS= read -r old_sha; do
    sed -i "s|${action}@${old_sha}|${action}@${sha}|g" "$target"
  done <<< "$current_shas"

  # Update the version comment on the line immediately above
  # each uses: line.  Pattern: a comment containing a version
  # like "# vX.Y.Z" or "# X.Y.Z".
  while IFS= read -r line_num; do
    if [ "$line_num" -le 1 ]; then
      continue
    fi
    prev_line=$((line_num - 1))
    prev_content=$(sed -n "${prev_line}p" "$target")
    if echo "$prev_content" | grep -qP '^\s*#\s*v?\d+\.\d+'; then
      indent=$(echo "$prev_content" | grep -oP '^\s*')
      sed -i "${prev_line}s|.*|${indent}# ${version}|" "$target"
    fi
  done < <(grep -n "uses:\s*${action}@" "$target" | cut -d: -f1)

  echo "  FIXED: ${filepath}"
done <<< "$RECORDS"

if [ "$DRIFT" -eq 1 ] && [ "$CHECK_ONLY" = true ]; then
  echo ""
  echo "Manifest drift detected. Run 'scripts/sync-actions-manifest.sh'" \
       "to fix."
  exit 1
fi

if [ "$DRIFT" -eq 0 ]; then
  echo "All action SHAs match the manifest."
fi
