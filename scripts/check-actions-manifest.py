#!/usr/bin/env python3
"""check-actions-manifest.py

Validates that actions-manifest.yml is complete and
consistent with the workflow and composite-action files.

Checks performed:
  1. Every SHA in the manifest matches the actual files.
  2. Every third-party "uses:" reference in repo YAML
     files appears in the manifest (no untracked actions).
  3. No action references use a plain version tag instead
     of a pinned SHA (e.g. @v4.1.1 instead of @abc123…).

Usage:
  scripts/check-actions-manifest.py          # from repo root
"""

import logging
import re
import sys
from pathlib import Path

import yaml

logging.basicConfig(format="%(message)s", level=logging.INFO)


class ManifestChecker:
    """Validates actions-manifest.yml against repo files."""

    REPO_ROOT = Path(__file__).resolve().parent.parent
    MANIFEST = REPO_ROOT / "actions-manifest.yml"
    # Matches: uses: owner/repo@<40-hex-char-sha>
    # Captures: group(1) = owner/repo, group(2) = sha
    USES_RE = re.compile(r"uses:\s+([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)@([0-9a-f]+)")

    # Matches any uses: owner/repo@<ref> — including tags, branches,
    # and SHAs.  Used to detect references that are NOT SHA-pinned.
    # Captures: group(1) = owner/repo, group(2) = ref (tag, branch, or sha)
    ANY_USES_RE = re.compile(r"uses:\s+([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)@(\S+)")

    # 40-character lower-case hex string — the format of a full git SHA.
    _SHA_RE = re.compile(r"^[0-9a-f]{40}$")

    # Directories to scan for untracked action references.
    SCAN_DIRS = [".github/workflows", "actions"]

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._errors = 0

    def _load_manifest(self):
        """Read and parse actions-manifest.yml."""
        with open(self.MANIFEST) as fh:
            return yaml.safe_load(fh)

    def _check_shas(self, manifest):
        """Check 1: every manifest SHA matches the actual files."""
        self._logger.info("=== Check 1: Manifest SHAs match workflow files ===")

        for entry in manifest.get("actions", []):
            action = entry.get("action", "")
            sha = entry.get("sha", "")
            version = entry.get("version", "")

            for rel_path in entry.get("used_in", []):
                self._verify_sha(rel_path, action, sha, version)

    def _verify_sha(self, rel_path, action, sha, version):
        """Compare a single action SHA in a workflow file."""
        target = self.REPO_ROOT / rel_path
        if not target.is_file():
            self._logger.info(
                "  FAIL: %s listed in manifest but file not found",
                rel_path,
            )
            self._errors += 1
            return

        text = target.read_text()
        found_shas = set(self.USES_RE.findall(text))
        action_shas = {s for a, s in found_shas if a == action}

        if not action_shas:
            self._logger.info("  FAIL: %s not found in %s", action, rel_path)
            self._errors += 1
            return

        if len(action_shas) > 1:
            self._logger.info("  FAIL: %s: %s has mixed SHAs:", rel_path, action)
            for s in sorted(action_shas):
                self._logger.info("        %s", s)
            self._errors += 1
            return

        actual_sha = action_shas.pop()
        if actual_sha != sha:
            self._logger.info("  FAIL: %s: %s", rel_path, action)
            self._logger.info("        manifest: %s (%s)", sha, version)
            self._logger.info("        actual:   %s", actual_sha)
            self._errors += 1
        else:
            self._logger.info("  OK:   %s: %s@%s", rel_path, action, version)

    def _check_untracked(self, manifest):
        """Check 2: every third-party action in repo is tracked."""
        self._logger.info("")
        self._logger.info("=== Check 2: All actions in repo are in the manifest ===")

        manifested = {entry.get("action", "") for entry in manifest.get("actions", [])}

        for rel_dir in self.SCAN_DIRS:
            scan_dir = self.REPO_ROOT / rel_dir
            if not scan_dir.is_dir():
                continue
            for yaml_file in sorted(scan_dir.rglob("*.yml")):
                self._check_file(yaml_file, manifested)
            for yaml_file in sorted(scan_dir.rglob("*.yaml")):
                self._check_file(yaml_file, manifested)

    def _check_file(self, yaml_file, manifested):
        """Scan a single file for untracked actions."""
        rel_path = yaml_file.relative_to(self.REPO_ROOT)
        text = yaml_file.read_text()
        refs = set(self.USES_RE.findall(text))

        for action, _ in refs:
            if action not in manifested:
                self._logger.info(
                    "  FAIL: %s uses %s which is NOT in the manifest",
                    rel_path,
                    action,
                )
                self._errors += 1

    def _check_unpinned(self):
        """Check 3: no action ref uses a tag/branch instead of a SHA."""
        self._logger.info("")
        self._logger.info("=== Check 3: All action refs are SHA-pinned ===")

        for rel_dir in self.SCAN_DIRS:
            scan_dir = self.REPO_ROOT / rel_dir
            if not scan_dir.is_dir():
                continue
            for yaml_file in sorted(scan_dir.rglob("*.yml")):
                self._check_file_pinned(yaml_file)
            for yaml_file in sorted(scan_dir.rglob("*.yaml")):
                self._check_file_pinned(yaml_file)

    def _check_file_pinned(self, yaml_file):
        """Flag any uses: lines whose ref is not a full 40-char hex SHA."""
        rel_path = yaml_file.relative_to(self.REPO_ROOT)
        text = yaml_file.read_text()

        for match in self.ANY_USES_RE.finditer(text):
            action = match.group(1)
            ref = match.group(2)
            if not self._SHA_RE.match(ref):
                self._logger.info(
                    "  FAIL: %s uses %s@%s — not a pinned SHA",
                    rel_path,
                    action,
                    ref,
                )
                self._errors += 1

    def run(self):
        """Execute all checks and exit non-zero on failure."""
        if not self.MANIFEST.is_file():
            self._logger.error("ERROR: Manifest not found at %s", self.MANIFEST)
            sys.exit(1)

        manifest = self._load_manifest()
        self._check_shas(manifest)
        self._check_untracked(manifest)
        self._check_unpinned()

        self._logger.info("")
        if self._errors > 0:
            self._logger.info("FAILED: %d issue(s) found.", self._errors)
            self._logger.info(
                "Run 'scripts/sync-actions-manifest.py' to fix SHA drift,"
            )
            self._logger.info("or add missing actions to actions-manifest.yml.")
            sys.exit(1)
        else:
            self._logger.info("PASSED: Manifest is complete and consistent.")

    @staticmethod
    def main():
        """Entry point."""
        ManifestChecker().run()


if __name__ == "__main__":
    ManifestChecker.main()
