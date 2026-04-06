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
import logging
import re
import sys
from pathlib import Path

import yaml

logging.basicConfig(format="%(message)s", level=logging.INFO)


class ManifestSyncer:
    """Patches workflow files to match actions-manifest.yml."""

    REPO_ROOT = Path(__file__).resolve().parent.parent
    MANIFEST = REPO_ROOT / "actions-manifest.yml"
    # Matches a YAML comment that starts with a version string, e.g.
    # "  # v6.0.2" or "  # 2.3.33".  Captures the leading whitespace
    # so the replacement can preserve indentation.
    VERSION_COMMENT_RE = re.compile(r"^(\s*)#\s*v?\d+\.\d+")

    # Matches a yamllint inline-disable comment, e.g.
    # "  # yamllint disable-line rule:line-length".
    # Used to detect the two-line pattern where a version comment
    # sits above a yamllint disable comment, which sits above uses:.
    YAMLLINT_DISABLE_RE = re.compile(
        r"^\s*#\s*yamllint\s+disable-line\s+"
    )

    def __init__(self, check_only=False):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._check_only = check_only
        self._drift = False

    def _load_manifest(self):
        """Read and parse actions-manifest.yml."""
        with open(self.MANIFEST) as fh:
            return yaml.safe_load(fh)

    def _sync_entry(self, action, sha, version, rel_path):
        """Sync a single action reference in one workflow file."""
        target = self.REPO_ROOT / rel_path
        if not target.is_file():
            self._logger.warning(
                "WARN: %s listed in manifest but not found", rel_path
            )
            return

        lines = target.read_text().splitlines(keepends=True)

        # Dynamic pattern for this specific action, e.g.
        # (uses:\s+actions/checkout@)([0-9a-f]+)
        # Captures: group(1) = prefix up to @, group(2) = current sha
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
            self._logger.warning(
                "WARN: %s not found in %s", action, rel_path
            )
            return

        if current_shas == {sha}:
            return

        self._logger.info(
            "DRIFT: %s: %s -> @%s (%s)", rel_path, action, sha, version
        )
        self._drift = True

        if self._check_only:
            return

        new_lines = self._patch_lines(lines, uses_re, sha, version)
        target.write_text("".join(new_lines))
        self._logger.info("  FIXED: %s", rel_path)

    def _patch_lines(self, lines, uses_re, sha, version):
        """Replace SHAs and update version comments."""
        new_lines = []
        for i, line in enumerate(lines):
            match = uses_re.search(line)
            if match:
                line = uses_re.sub(rf"\g<1>{sha}", line)

                # Update the version comment above the uses: line.
                # One-line pattern: version comment directly above.
                # Two-line pattern: version comment, then a
                # yamllint disable-line comment, then uses:.
                if (i > 0
                        and self.VERSION_COMMENT_RE.match(
                            new_lines[i - 1])):
                    indent = re.match(
                        r"(\s*)", new_lines[i - 1]
                    ).group(1)
                    new_lines[i - 1] = "%s# %s\n" % (indent, version)
                elif (i > 1
                      and self.YAMLLINT_DISABLE_RE.match(
                          new_lines[i - 1])
                      and self.VERSION_COMMENT_RE.match(
                          new_lines[i - 2])):
                    indent = re.match(
                        r"(\s*)", new_lines[i - 2]
                    ).group(1)
                    new_lines[i - 2] = "%s# %s\n" % (indent, version)

            new_lines.append(line)
        return new_lines

    def run(self):
        """Sync all manifest entries and report results."""
        if not self.MANIFEST.is_file():
            self._logger.error(
                "ERROR: Manifest not found at %s", self.MANIFEST
            )
            sys.exit(1)

        manifest = self._load_manifest()

        for entry in manifest.get("actions", []):
            action = entry.get("action", "")
            sha = entry.get("sha", "")
            version = entry.get("version", "")

            for rel_path in entry.get("used_in", []):
                self._sync_entry(action, sha, version, rel_path)

        if self._drift and self._check_only:
            self._logger.info("")
            self._logger.info(
                "Manifest drift detected.  "
                "Run 'scripts/sync-actions-manifest.py' to fix."
            )
            sys.exit(1)

        if not self._drift:
            self._logger.info("All action SHAs match the manifest.")

    @staticmethod
    def main():
        """Entry point."""
        parser = argparse.ArgumentParser(
            description="Sync workflow files from actions-manifest.yml"
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Exit 1 on drift without making changes",
        )
        args = parser.parse_args()

        ManifestSyncer(check_only=args.check).run()


if __name__ == "__main__":
    ManifestSyncer.main()
