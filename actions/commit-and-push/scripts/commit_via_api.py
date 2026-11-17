#!/usr/bin/env python3
"""commit_via_api.py

Commits local changes to the checked-out branch through GitHub's
GraphQL ``createCommitOnBranch`` mutation instead of ``git push``.

GitHub signs commits that a GitHub App (or ``GITHUB_TOKEN``) makes
through the API, so they show as "Verified" and pass a "Require
signed commits" ruleset.  The commit author is the token's bot;
setting a custom author would make the commit unsigned.

If the branch moves while the job runs, the local changes are
re-applied on top of the new head (like ``git pull --rebase
--autostash``) and the commit is retried.

Usage:
  actions/commit-and-push/scripts/commit_via_api.py   # via action.yml
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Callable, Mapping

logging.basicConfig(format="%(message)s", level=logging.INFO)

# Sends a GraphQL request body and returns the decoded JSON response.
Transport = Callable[[dict], dict]


class HeadMovedError(Exception):
    """The branch head on GitHub is no longer ``expectedHeadOid``."""


class ApiCommitter:
    """Commits changed files to the current branch via the GraphQL API."""

    MUTATION: str = (
        "mutation($input: CreateCommitOnBranchInput!) {"
        " createCommitOnBranch(input: $input) { commit { oid url } } }"
    )

    # GitHub's error text when ``expectedHeadOid`` is stale.
    HEAD_MOVED_TEXT: str = "Expected branch to point to"

    # Captures ``owner/repo`` from https, ssh or proxied remote URLs.
    REMOTE_RE: re.Pattern[str] = re.compile(r"[:/]([^/:]+/[^/]+?)(?:\.git)?/?$")

    MAX_ATTEMPTS: int = 3

    def __init__(
        self,
        env: Mapping[str, str],
        transport: Transport | None = None,
        repository: str | None = None,
    ) -> None:
        """Store the inputs.

        ``env`` holds ``INPUT_FILE_PATH`` (space-separated pathspecs),
        ``INPUT_COMMIT_MESSAGE``, ``GITHUB_TOKEN`` and optionally
        ``GITHUB_GRAPHQL_URL``.  ``transport`` and ``repository``
        override the HTTP call and the ``owner/repo`` read from the
        ``origin`` remote; tests use them.
        """
        self._env: Mapping[str, str] = env
        self._pathspecs: list[str] = env.get("INPUT_FILE_PATH", "").split()
        self._message: str = env.get("INPUT_COMMIT_MESSAGE", "")
        self._transport: Transport = transport or self._post_graphql
        self._repository: str | None = repository
        self._logger: logging.Logger = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def _git(*args: str) -> str:
        """Run ``git`` in the current directory and return its stdout."""
        result = subprocess.run(
            ["git", *args], check=True, capture_output=True, text=True
        )
        return result.stdout

    def repository(self) -> str:
        """Return ``owner/repo`` of the ``origin`` remote."""
        if self._repository:
            return self._repository
        url: str = self._git("remote", "get-url", "origin").strip()
        match = self.REMOTE_RE.search(url)
        if not match:
            raise ValueError(f"Cannot read owner/repo from origin URL {url!r}")
        return match.group(1)

    def branch(self) -> str:
        """Return the checked-out branch; fail on a detached HEAD."""
        try:
            return self._git("symbolic-ref", "--short", "HEAD").strip()
        except subprocess.CalledProcessError as err:
            raise ValueError(
                "HEAD is detached; check out the branch to commit to"
            ) from err

    @staticmethod
    def _git_bytes(*args: str) -> bytes:
        """Run ``git`` in the current directory and return raw stdout."""
        result = subprocess.run(["git", *args], check=True, capture_output=True)
        return result.stdout

    def changed_paths(self) -> list[str]:
        """Return the root-relative paths that ``git status`` shows as changed."""
        status: str = self._git(
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--",
            *self._pathspecs,
        )
        entries: list[str] = status.split("\0")
        paths: list[str] = []
        index: int = 0
        while index < len(entries):
            entry: str = entries[index]
            index += 1
            if not entry:
                continue
            paths.append(entry[3:])
            if entry[0] in "RC":
                # A staged rename or copy is followed by its source path.
                paths.append(entries[index])
                index += 1
        return paths

    def index_modes(self, root: str, paths: list[str]) -> dict[str, str]:
        """Return the index file mode of each of ``paths`` that is in the index."""
        listing: str = self._git("-C", root, "ls-files", "--stage", "-z", "--", *paths)
        modes: dict[str, str] = {}
        for entry in listing.split("\0"):
            if entry:
                info, _, path = entry.partition("\t")
                modes[path] = info.split(" ")[0]
        return modes

    def file_changes(self) -> dict:
        """Return the ``FileChanges`` input for the changed pathspecs.

        The changes are staged first and read back from the index, so
        Git's clean filters (Git LFS pointers, line endings) apply and a
        deleted-then-recreated file shows as one change.
        """
        if self._git("ls-files", "--unmerged"):
            raise ValueError("The checkout has unresolved merge conflicts")
        root: str = self._git("rev-parse", "--show-toplevel").strip()
        paths: list[str] = self.changed_paths()
        if not paths:
            return {"additions": [], "deletions": []}
        modes: dict[str, str] = self.index_modes(root, paths)
        # ``git add`` fails on a path that is in neither the index nor the tree.
        addable: list[str] = [
            path
            for path in paths
            if path in modes or os.path.lexists(os.path.join(root, path))
        ]
        if addable:
            self._git("-C", root, "add", "--all", "--", *addable)
        diff: str = self._git(
            "-C",
            root,
            "diff",
            "--cached",
            "--no-renames",
            "--name-status",
            "-z",
            "HEAD",
            "--",
            *paths,
        )
        fields: list[str] = diff.split("\0")
        modes = self.index_modes(root, paths)
        additions: list[dict] = []
        deletions: list[dict] = []
        for code, path in zip(fields[0::2], fields[1::2]):
            if code == "D":
                deletions.append({"path": path})
                continue
            if modes.get(path) == "120000":
                raise ValueError(f"{path} is a symlink; the API cannot commit it")
            contents: bytes = self._git_bytes(
                "-C", root, "cat-file", "blob", f":{path}"
            )
            additions.append(
                {"path": path, "contents": base64.b64encode(contents).decode()}
            )
        return {"additions": additions, "deletions": deletions}

    def _post_graphql(self, body: dict) -> dict:
        """POST ``body`` to the GraphQL API and return the JSON reply."""
        url: str = (
            self._env.get("GITHUB_GRAPHQL_URL") or "https://api.github.com/graphql"
        )
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"bearer {self._env.get('GITHUB_TOKEN', '')}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as err:
            raise RuntimeError(
                f"GraphQL request failed: HTTP {err.code} {err.read().decode()}"
            ) from err

    def create_commit(self, branch: str, head: str, changes: dict) -> dict:
        """Create the commit on ``branch`` whose head must be ``head``."""
        headline, _, body = self._message.partition("\n")
        reply: dict = self._transport(
            {
                "query": self.MUTATION,
                "variables": {
                    "input": {
                        "branch": {
                            "repositoryNameWithOwner": self.repository(),
                            "branchName": branch,
                        },
                        "message": {"headline": headline, "body": body.strip()},
                        "expectedHeadOid": head,
                        "fileChanges": changes,
                    }
                },
            }
        )
        errors: list[dict] = reply.get("errors") or []
        if errors:
            text: str = "; ".join(error.get("message", "") for error in errors)
            if self.HEAD_MOVED_TEXT in text:
                raise HeadMovedError(text)
            raise RuntimeError(f"createCommitOnBranch failed: {text}")
        return reply.get("data", {}).get("createCommitOnBranch", {}).get("commit", {})

    def rebase_onto_remote(self, branch: str) -> None:
        """Re-apply the local changes on top of the remote branch head."""
        self._git("fetch", "--quiet", "origin", branch)
        # Stash the whole tree: a pathspec of a deleted file fails.
        self._git("stash", "push", "--include-untracked", "--quiet")
        self._git("merge", "--ff-only", "--quiet", "FETCH_HEAD")
        try:
            self._git("stash", "pop", "--quiet")
        except subprocess.CalledProcessError as err:
            raise RuntimeError(
                f"Local changes conflict with the new head of {branch}: "
                f"{err.stderr.strip()}"
            ) from err

    def run(self) -> str | None:
        """Commit the changes; return the new commit SHA, or None if none."""
        if not self._pathspecs or not self._message:
            raise ValueError("file_path and commit_message are required")
        branch: str = self.branch()
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            changes: dict = self.file_changes()
            if not changes.get("additions") and not changes.get("deletions"):
                self._logger.info("No changes to commit.")
                return None
            head: str = self._git("rev-parse", "HEAD").strip()
            try:
                commit: dict = self.create_commit(branch, head, changes)
            except HeadMovedError:
                if attempt == self.MAX_ATTEMPTS:
                    raise
                self._logger.info("%s moved; rebasing and retrying.", branch)
                self.rebase_onto_remote(branch)
                continue
            self._logger.info("Committed %s", commit.get("url", commit.get("oid")))
            return commit.get("oid")
        return None

    @staticmethod
    def main() -> None:
        """Entry point."""
        try:
            ApiCommitter(os.environ).run()
        except (ValueError, RuntimeError, HeadMovedError, OSError) as err:
            logging.getLogger(ApiCommitter.__name__).error("::error::%s", err)
            sys.exit(1)
        except subprocess.CalledProcessError as err:
            logging.getLogger(ApiCommitter.__name__).error(
                "::error::%s failed: %s", " ".join(err.cmd), err.stderr.strip()
            )
            sys.exit(1)


if __name__ == "__main__":
    ApiCommitter.main()
