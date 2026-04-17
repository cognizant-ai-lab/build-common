#!/usr/bin/env python3
"""sync_actions_manifest.py

Reads actions-manifest.yml and patches every workflow /
composite-action file so that pinned SHAs and version
comments match the manifest.

Usage:
  scripts/sync_actions_manifest.py              # from repo root
  scripts/sync_actions_manifest.py --check      # exit 1 on drift
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(format="%(message)s", level=logging.INFO)


class ManifestSyncer:
    """Patches workflow files to match actions-manifest.yml."""

    REPO_ROOT: Path = Path(__file__).resolve().parent.parent
    MANIFEST: Path = REPO_ROOT / "actions-manifest.yml"
    # Matches a YAML comment that starts with a version string, e.g.
    # "  # v6.0.2" or "  # 2.3.33".  Captures the leading whitespace
    # so the replacement can preserve indentation.
    VERSION_COMMENT_RE: re.Pattern[str] = re.compile(r"^(\s*)#\s*v?\d+\.\d+")

    # Matches a yamllint inline-disable comment, e.g.
    # "  # yamllint disable-line rule:line-length".
    # Used to detect the two-line pattern where a version comment
    # sits above a yamllint disable comment, which sits above uses:.
    YAMLLINT_DISABLE_RE: re.Pattern[str] = re.compile(
        r"^\s*#\s*yamllint\s+disable-line\s+"
    )

    def __init__(self, check_only: bool = False) -> None:
        self._logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self._check_only: bool = check_only
        self._drift: bool = False

    def _load_manifest(self) -> dict[str, Any]:
        """Read and parse actions-manifest.yml."""
        with open(self.MANIFEST) as fh:
            manifest: dict[str, Any] = yaml.safe_load(fh)
            return manifest

    def _sync_entry(self, action: str, sha: str, version: str, rel_path: str) -> None:
        """Sync a single action reference in one workflow file."""
        target: Path = self.REPO_ROOT / rel_path
        if not target.is_file():
            self._logger.warning("WARN: %s listed in manifest but not found", rel_path)
            return

        lines: list[str] = target.read_text().splitlines(keepends=True)

        # Dynamic pattern for this specific action, e.g.
        # (uses:\s+actions/checkout@)([0-9a-f]+)
        # Captures: group(1) = prefix up to @, group(2) = current sha
        uses_re: re.Pattern[str] = re.compile(
            rf"(uses:\s+{re.escape(action)}@)([0-9a-f]+)"
        )

        # Collect unique SHAs currently present for this action.
        current_shas: set[str] = set()
        for line in lines:
            match: re.Match[str] | None = uses_re.search(line)
            if match:
                current_shas.add(match.group(2))

        if not current_shas:
            self._logger.warning("WARN: %s not found in %s", action, rel_path)
            return

        if current_shas == {sha}:
            return

        self._logger.info("DRIFT: %s: %s -> @%s (%s)", rel_path, action, sha, version)
        self._drift = True

        if self._check_only:
            return

        new_lines: list[str] = self._patch_lines(lines, uses_re, sha, version)
        target.write_text("".join(new_lines))
        self._logger.info("  FIXED: %s", rel_path)

    def _patch_lines(
        self,
        lines: list[str],
        uses_re: re.Pattern[str],
        sha: str,
        version: str,
    ) -> list[str]:
        """Replace SHAs and update version comments."""
        new_lines: list[str] = []
        for i, line in enumerate(lines):
            match: re.Match[str] | None = uses_re.search(line)
            if match:
                line = uses_re.sub(rf"\g<1>{sha}", line)

                # Update the version comment above the uses: line.
                # One-line pattern: version comment directly above.
                # Two-line pattern: version comment, then a
                # yamllint disable-line comment, then uses:.
                if i > 0 and self.VERSION_COMMENT_RE.match(new_lines[i - 1]):
                    indent_match: re.Match[str] | None = re.match(
                        r"(\s*)", new_lines[i - 1]
                    )
                    indent: str = indent_match.group(1) if indent_match else ""
                    new_lines[i - 1] = "%s# %s\n" % (indent, version)
                elif (
                    i > 1
                    and self.YAMLLINT_DISABLE_RE.match(new_lines[i - 1])
                    and self.VERSION_COMMENT_RE.match(new_lines[i - 2])
                ):
                    indent_match2: re.Match[str] | None = re.match(
                        r"(\s*)", new_lines[i - 2]
                    )
                    indent: str = indent_match2.group(1) if indent_match2 else ""
                    new_lines[i - 2] = "%s# %s\n" % (indent, version)

            new_lines.append(line)
        return new_lines

    def run(self) -> None:
        """Sync all manifest entries and report results."""
        if not self.MANIFEST.is_file():
            self._logger.error("ERROR: Manifest not found at %s", self.MANIFEST)
            sys.exit(1)

        manifest: dict[str, Any] = self._load_manifest()

        for entry in manifest.get("actions", []):
            action: str = entry.get("action", "")
            sha: str = entry.get("sha", "")
            version: str = entry.get("version", "")

            for rel_path in entry.get("used_in", []):
                self._sync_entry(action, sha, version, rel_path)

        if self._drift and self._check_only:
            self._logger.info("")
            self._logger.info(
                "Manifest drift detected.  "
                "Run 'scripts/sync_actions_manifest.py' to fix."
            )
            sys.exit(1)

        if not self._drift:
            self._logger.info("All action SHAs match the manifest.")

    @staticmethod
    def main() -> None:
        """Entry point."""
        parser: argparse.ArgumentParser = argparse.ArgumentParser(
            description="Sync workflow files from actions-manifest.yml"
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Exit 1 on drift without making changes",
        )
        args: argparse.Namespace = parser.parse_args()

        ManifestSyncer(check_only=args.check).run()


if __name__ == "__main__":
    ManifestSyncer.main()
