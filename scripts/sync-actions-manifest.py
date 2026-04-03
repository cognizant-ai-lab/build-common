#!/usr/bin/env python3
"""sync-actions-manifest.py

Reads actions-manifest.yml and patches every workflow /
composite-action file so that pinned SHAs and version
comments match the manifest.

Usage:
  scripts/sync-actions-manifest.py              # from repo root
  scripts/sync-actions-manifest.py --check      # exit 1 on drift
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "actions-manifest.yml"
VERSION_COMMENT_RE = re.compile(r"^(\s*)#\s*v?\d+\.\d+")
YAMLLINT_DISABLE_RE = re.compile(r"^\s*#\s*yamllint\s+disable-line\s+")


def load_manifest():
    with open(MANIFEST) as fh:
        return yaml.safe_load(fh)


def sync(manifest, check_only):
    """Patch workflow files to match the manifest.

    Returns True if any drift was detected.
    """
    drift = False

    for entry in manifest["actions"]:
        action = entry["action"]
        sha = entry["sha"]
        version = entry["version"]

        for rel_path in entry["used_in"]:
            target = REPO_ROOT / rel_path
            if not target.is_file():
                print(f"WARN: {rel_path} listed in manifest but not found",
                      file=sys.stderr)
                continue

            lines = target.read_text().splitlines(keepends=True)
            uses_re = re.compile(
                rf"(uses:\s+{re.escape(action)}@)([0-9a-f]+)"
            )

            # Collect unique SHAs currently present for this action.
            current_shas = set()
            for line in lines:
                match = uses_re.search(line)
                if match:
                    current_shas.add(match.group(2))

            if not current_shas:
                print(f"WARN: {action} not found in {rel_path}",
                      file=sys.stderr)
                continue

            if current_shas == {sha}:
                continue

            print(f"DRIFT: {rel_path}: {action} -> @{sha} ({version})")
            drift = True

            if check_only:
                continue

            # Replace SHAs and update version comments.
            new_lines = []
            for i, line in enumerate(lines):
                match = uses_re.search(line)
                if match:
                    line = uses_re.sub(rf"\g<1>{sha}", line)

                    # Update the version comment above the uses: line.
                    # One-line pattern: version comment directly above.
                    # Two-line pattern: version comment, then a
                    # yamllint disable-line comment, then uses:.
                    if i > 0 and VERSION_COMMENT_RE.match(new_lines[i - 1]):
                        indent = re.match(r"(\s*)", new_lines[i - 1]).group(1)
                        new_lines[i - 1] = f"{indent}# {version}\n"
                    elif (i > 1
                          and YAMLLINT_DISABLE_RE.match(new_lines[i - 1])
                          and VERSION_COMMENT_RE.match(new_lines[i - 2])):
                        indent = re.match(r"(\s*)", new_lines[i - 2]).group(1)
                        new_lines[i - 2] = f"{indent}# {version}\n"

                new_lines.append(line)

            target.write_text("".join(new_lines))
            print(f"  FIXED: {rel_path}")

    return drift


def main():
    parser = argparse.ArgumentParser(
        description="Sync workflow files from actions-manifest.yml"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 on drift without making changes",
    )
    args = parser.parse_args()

    if not MANIFEST.is_file():
        print(f"ERROR: Manifest not found at {MANIFEST}", file=sys.stderr)
        sys.exit(1)

    manifest = load_manifest()
    drift = sync(manifest, check_only=args.check)

    if drift and args.check:
        print("")
        print("Manifest drift detected. Run 'scripts/sync-actions-manifest.py'"
              " to fix.")
        sys.exit(1)

    if not drift:
        print("All action SHAs match the manifest.")


if __name__ == "__main__":
    main()
