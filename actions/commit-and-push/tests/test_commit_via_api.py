"""Tests for the commit-and-push ``commit_via_api`` script.

Each test runs against real git repositories in ``tmp_path`` (a bare
``origin`` plus a clone) and a fake GraphQL transport, so no network
access is needed.
"""

from __future__ import annotations

import base64
import os
import subprocess
from pathlib import Path

import pytest

from commit_via_api import ApiCommitter, HeadMovedError


class FakeTransport:
    """Records GraphQL requests and replays canned replies."""

    def __init__(self, *replies: dict) -> None:
        """Store the replies to return, in order."""
        self.replies: list[dict] = list(replies)
        self.requests: list[dict] = []

    def __call__(self, body: dict) -> dict:
        """Record ``body`` and return the next reply."""
        self.requests.append(body["variables"]["input"])
        return self.replies.pop(0)


OK: dict = {"data": {"createCommitOnBranch": {"commit": {"oid": "abc", "url": "u"}}}}
MOVED: dict = {"errors": [{"message": 'Expected branch to point to "x"'}]}


class TestApiCommitter:
    """Tests for ``ApiCommitter``."""

    @staticmethod
    def _git(cwd: Path, *args: str) -> str:
        """Run git in ``cwd`` and return stdout."""
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    @pytest.fixture
    def clone(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Return a clone of a bare origin with ``values.yaml`` on main."""
        origin: Path = tmp_path / "origin.git"
        self._git(tmp_path, "init", "--quiet", "--bare", "-b", "main", str(origin))
        work: Path = tmp_path / "work"
        self._git(tmp_path, "clone", "--quiet", str(origin), str(work))
        (work / "values.yaml").write_text("a: 1\nkeep\nb: 1\n")
        (work / "other.yaml").write_text("x\n")
        self._git(work, "add", ".")
        self._git(work, "commit", "--quiet", "-m", "init")
        self._git(work, "push", "--quiet", "origin", "main")
        monkeypatch.chdir(work)
        return work

    @staticmethod
    def _committer(
        transport: FakeTransport, files: str = "values.yaml"
    ) -> ApiCommitter:
        """Return a committer for ``files`` using ``transport``."""
        env: dict = {"INPUT_FILE_PATH": files, "INPUT_COMMIT_MESSAGE": "Bump\n\nbody"}
        return ApiCommitter(env, transport=transport, repository="org/repo")

    def test_commits_changed_file(self, clone: Path) -> None:
        """A changed file is sent as an addition against the local HEAD."""
        (clone / "values.yaml").write_text("a: 2\nkeep\nb: 1\n")
        (clone / "other.yaml").write_text("not selected\n")
        transport = FakeTransport(OK)
        assert self._committer(transport).run() == "abc"
        request: dict = transport.requests[0]
        assert request["branch"] == {
            "repositoryNameWithOwner": "org/repo",
            "branchName": "main",
        }
        assert request["message"] == {"headline": "Bump", "body": "body"}
        assert request["expectedHeadOid"] == self._git(clone, "rev-parse", "HEAD")
        contents: str = base64.b64encode(b"a: 2\nkeep\nb: 1\n").decode()
        assert request["fileChanges"] == {
            "additions": [{"path": "values.yaml", "contents": contents}],
            "deletions": [],
        }

    def test_multiple_files_new_and_deleted(self, clone: Path) -> None:
        """Space-separated pathspecs cover new, changed and deleted files."""
        (clone / "new.yaml").write_text("n\n")
        os.remove(clone / "other.yaml")
        transport = FakeTransport(OK)
        self._committer(transport, "new.yaml other.yaml values.yaml").run()
        changes: dict = transport.requests[0]["fileChanges"]
        assert [a["path"] for a in changes["additions"]] == ["new.yaml"]
        assert changes["deletions"] == [{"path": "other.yaml"}]

    def test_staged_replacement_is_one_change(self, clone: Path) -> None:
        """A staged deletion that is recreated is sent once, as an addition."""
        self._git(clone, "rm", "--quiet", "values.yaml")
        (clone / "values.yaml").write_text("new\n")
        transport = FakeTransport(OK)
        self._committer(transport).run()
        changes: dict = transport.requests[0].get("fileChanges")
        assert [a.get("path") for a in changes.get("additions")] == ["values.yaml"]
        assert changes.get("deletions") == []

    def test_clean_filter_applies(self, clone: Path) -> None:
        """Contents come from the index, so clean filters such as Git LFS apply."""
        self._git(clone, "config", "filter.upper.clean", "tr a-z A-Z")
        (clone / ".gitattributes").write_text("values.yaml filter=upper\n")
        (clone / "values.yaml").write_text("changed\n")
        transport = FakeTransport(OK)
        self._committer(transport).run()
        addition: dict = transport.requests[0].get("fileChanges").get("additions")[0]
        assert base64.b64decode(addition.get("contents")) == b"CHANGED\n"

    def test_symlink_fails(self, clone: Path) -> None:
        """A symlink is refused instead of committing its target's contents."""
        os.symlink("/etc/hostname", clone / "link.yaml")
        with pytest.raises(ValueError, match="symlink"):
            self._committer(FakeTransport(), "link.yaml").run()

    def test_unmerged_fails(self, clone: Path, tmp_path: Path) -> None:
        """Conflict-marked files are not committed."""
        self._push_other_change(tmp_path, "a: 3\nkeep\nb: 1\n")
        (clone / "values.yaml").write_text("a: 2\nkeep\nb: 1\n")
        self._git(clone, "commit", "--quiet", "-am", "local")
        subprocess.run(["git", "pull", "--quiet", "--no-rebase"], cwd=clone)
        with pytest.raises(ValueError, match="conflicts"):
            self._committer(FakeTransport()).run()

    def test_no_changes(self, clone: Path) -> None:
        """No API call is made when nothing changed."""
        transport = FakeTransport()
        assert self._committer(transport).run() is None
        assert not transport.requests

    def _push_other_change(self, tmp_path: Path, text: str) -> Path:
        """Push a change to ``values.yaml`` from a second clone."""
        other: Path = tmp_path / "other"
        origin: str = str(tmp_path / "origin.git")
        self._git(tmp_path, "clone", "--quiet", origin, str(other))
        (other / "values.yaml").write_text(text)
        self._git(other, "commit", "--quiet", "-am", "other")
        self._git(other, "push", "--quiet", "origin", "main")
        return other

    def test_retries_after_head_moved(self, clone: Path, tmp_path: Path) -> None:
        """When main moves, the change is rebased onto the new head and retried."""
        other: Path = self._push_other_change(tmp_path, "a: 1\nkeep\nb: 2\n")
        (clone / "values.yaml").write_text("a: 2\nkeep\nb: 1\n")
        self._git(clone, "rm", "--quiet", "other.yaml")
        transport = FakeTransport(MOVED, OK)
        assert self._committer(transport, "values.yaml other.yaml").run() == "abc"
        retry: dict = transport.requests[1]
        assert retry["fileChanges"]["deletions"] == [{"path": "other.yaml"}]
        assert retry["expectedHeadOid"] == self._git(other, "rev-parse", "HEAD")
        contents: str = retry["fileChanges"]["additions"][0]["contents"]
        assert base64.b64decode(contents) == b"a: 2\nkeep\nb: 2\n"

    def test_conflict_fails(self, clone: Path, tmp_path: Path) -> None:
        """A remote change to the same line cannot be rebased."""
        self._push_other_change(tmp_path, "a: 3\nkeep\nb: 1\n")
        (clone / "values.yaml").write_text("a: 2\nkeep\nb: 1\n")
        with pytest.raises(RuntimeError, match="conflict"):
            self._committer(FakeTransport(MOVED)).run()

    def test_gives_up_after_max_attempts(self, clone: Path) -> None:
        """A head that keeps moving fails after ``MAX_ATTEMPTS``."""
        (clone / "values.yaml").write_text("a: 2\nkeep\nb: 1\n")
        transport = FakeTransport(*[MOVED] * ApiCommitter.MAX_ATTEMPTS)
        with pytest.raises(HeadMovedError):
            self._committer(transport).run()

    def test_other_error_fails(self, clone: Path) -> None:
        """Any other GraphQL error is raised."""
        (clone / "values.yaml").write_text("a: 2\nkeep\nb: 1\n")
        error: dict = {"errors": [{"message": "Resource not accessible"}]}
        transport = FakeTransport(error)
        with pytest.raises(RuntimeError, match="Resource not accessible"):
            self._committer(transport).run()

    def test_detached_head_fails(self, clone: Path) -> None:
        """A detached HEAD has no branch to commit to."""
        self._git(clone, "checkout", "--quiet", "--detach")
        with pytest.raises(ValueError, match="detached"):
            self._committer(FakeTransport()).run()

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/org/repo",
            "https://github.com/org/repo.git",
            "git@github.com:org/repo.git",
            "https://git-manager.devin.ai/proxy/github.com/org/repo",
        ],
    )
    def test_repository_from_origin(self, clone: Path, url: str) -> None:
        """``owner/repo`` is read from the origin URL."""
        self._git(clone, "remote", "set-url", "origin", url)
        assert ApiCommitter({}).repository() == "org/repo"
