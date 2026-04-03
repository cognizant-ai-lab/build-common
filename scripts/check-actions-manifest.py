#!/usr/bin/env python3
"""check-actions-manifest.py

Validates that actions-manifest.yml is complete and
consistent with the workflow and composite-action files.

Checks performed:
  1. Every SHA in the manifest matches the actual files.
  2. Every third-party "uses:" reference in repo YAML
     files appears in the manifest (no untracked actions).

Usage:
  scripts/check-actions-manifest.py          # from repo root
"""

import os
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "actions-manifest.yml"
USES_RE = re.compile(r"uses:\s+([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)@([0-9a-f]+)")


def load_manifest():
    with open(MANIFEST) as fh:
        return yaml.safe_load(fh)


def check_shas(manifest):
    """Check 1: every manifest SHA matches the actual files."""
    errors = 0
    print("=== Check 1: Manifest SHAs match workflow files ===")

    for entry in manifest["actions"]:
        action = entry["action"]
        sha = entry["sha"]
        version = entry["version"]

        for rel_path in entry["used_in"]:
            target = REPO_ROOT / rel_path
            if not target.is_file():
                print(f"  FAIL: {rel_path} listed in manifest but file not found")
                errors += 1
                continue

            text = target.read_text()
            found_shas = set(USES_RE.findall(text))
            # Filter to only matches for this action
            action_shas = {s for a, s in found_shas if a == action}

            if not action_shas:
                print(f"  FAIL: {action} not found in {rel_path}")
                errors += 1
                continue

            if len(action_shas) > 1:
                print(f"  FAIL: {rel_path}: {action} has mixed SHAs:")
                for s in sorted(action_shas):
                    print(f"        {s}")
                errors += 1
                continue

            actual_sha = action_shas.pop()
            if actual_sha != sha:
                print(f"  FAIL: {rel_path}: {action}")
                print(f"        manifest: {sha} ({version})")
                print(f"        actual:   {actual_sha}")
                errors += 1
            else:
                print(f"  OK:   {rel_path}: {action}@{version}")

    return errors


def check_untracked(manifest):
    """Check 2: every third-party action in repo is in the manifest."""
    errors = 0
    print("")
    print("=== Check 2: All actions in repo are in the manifest ===")

    manifested = {entry["action"] for entry in manifest["actions"]}

    scan_dirs = [
        REPO_ROOT / ".github" / "workflows",
        REPO_ROOT / "actions",
    ]

    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for yaml_file in sorted(scan_dir.rglob("*.yml")):
            _check_file(yaml_file, manifested, errors_ref=[errors])
            errors = _check_file.last_errors
        for yaml_file in sorted(scan_dir.rglob("*.yaml")):
            _check_file(yaml_file, manifested, errors_ref=[errors])
            errors = _check_file.last_errors

    return errors


def _check_file(yaml_file, manifested, errors_ref):
    """Scan a single file for untracked actions."""
    errors = errors_ref[0]
    rel_path = yaml_file.relative_to(REPO_ROOT)
    text = yaml_file.read_text()
    refs = set(USES_RE.findall(text))

    for action, _ in refs:
        if action not in manifested:
            print(f"  FAIL: {rel_path} uses {action} which is NOT in the manifest")
            errors += 1

    _check_file.last_errors = errors


_check_file.last_errors = 0


def main():
    if not MANIFEST.is_file():
        print(f"ERROR: Manifest not found at {MANIFEST}", file=sys.stderr)
        sys.exit(1)

    manifest = load_manifest()
    errors = 0
    errors += check_shas(manifest)
    errors += check_untracked(manifest)

    print("")
    if errors > 0:
        print(f"FAILED: {errors} issue(s) found.")
        print("Run 'scripts/sync-actions-manifest.py' to fix SHA drift,")
        print("or add missing actions to actions-manifest.yml.")
        sys.exit(1)
    else:
        print("PASSED: Manifest is complete and consistent.")


if __name__ == "__main__":
    main()
