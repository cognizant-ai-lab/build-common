#!/usr/bin/env python3
"""Build the Slack webhook payload for the slack-notify action.

Reads inputs from the environment variables documented in
``action.yml`` and writes a ``payload=<json>`` multiline line to
``$GITHUB_OUTPUT`` so the downstream ``slackapi/slack-github-action``
step can POST it.

This replaces an earlier bash implementation that shelled out to
``jq``.  Python's standard library is present in every caller image
we target (including ``python:*-slim``), whereas ``jq`` is not, so
this removes a hidden host-level prerequisite for containerized
callers.  ``json.dumps`` provides the same JSON-escaping guarantee
that motivated using ``jq --null-input --arg`` originally.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Mapping


class SlackPayloadBuilder:
    """Builds the Slack webhook payload from the action's env inputs."""

    # Maps a job-status string to (slack emoji name, attachment color,
    # human-readable status text).  Unknown statuses fall back to a
    # neutral grey question mark and render the status verbatim.
    STATUS_MAP: dict[str, tuple[str, str, str]] = {
        "success": ("white_check_mark", "good", "Passed"),
        "failure": ("x", "danger", "Failed"),
        "cancelled": ("warning", "warning", "Cancelled"),
    }

    # Heredoc delimiter used when writing the multiline ``payload``
    # entry to ``$GITHUB_OUTPUT``.  Matches the original bash script
    # so the contract with the downstream action step stays stable.
    HEREDOC_DELIMITER: str = "PAYLOAD_EOF"

    def __init__(self, env: Mapping[str, str]) -> None:
        """Store the env mapping the payload will be built from.

        ``env`` is a mapping of the input environment variables set by
        ``action.yml`` (``INPUT_STATUS``, ``INPUT_MESSAGE``,
        ``INPUT_MENTION``, ``GH_REPO``, ``GH_REF``, ``GH_SERVER``,
        ``GH_RUN_ID``, ``GH_WORKFLOW``, ``GH_ACTOR``).
        """
        self._env: Mapping[str, str] = env

    def build_payload(self) -> dict:
        """Return the Slack webhook payload dict built from the env."""
        status: str = self._env["INPUT_STATUS"]
        emoji, color, status_text = self.STATUS_MAP.get(
            status,
            ("grey_question", "#808080", status),
        )

        message: str = self._env.get("INPUT_MESSAGE") or status_text

        mention: str = ""
        if status == "failure" and self._env.get("INPUT_MENTION") == "true":
            mention = "<!channel> "

        repo: str = self._env["GH_REPO"]
        ref: str = self._env["GH_REF"]
        run_url: str = (
            f"{self._env['GH_SERVER']}/{repo}/actions/runs/{self._env['GH_RUN_ID']}"
        )
        workflow: str = self._env["GH_WORKFLOW"]
        actor: str = self._env["GH_ACTOR"]

        section_text: str = (
            f"{mention}:{emoji}: *{message}* for "
            f"`{repo}` on `{ref}`\n"
            f"<{run_url}|View build run>"
        )
        context_text: str = f"Workflow: {workflow} | Triggered by: {actor}"

        return {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": section_text,
                            },
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": context_text,
                                },
                            ],
                        },
                    ],
                },
            ],
        }

    def format_github_output(self, payload: dict) -> str:
        """Return the ``payload=<json>`` multiline block for GITHUB_OUTPUT.

        Uses the standard ``<<DELIMITER ... DELIMITER`` heredoc form so
        the serialized JSON can safely contain newlines (``json.dumps``
        does not produce newlines by default, but the heredoc form
        matches the original bash implementation and keeps the contract
        stable).
        """
        serialized: str = json.dumps(payload)
        delimiter: str = self.HEREDOC_DELIMITER
        return f"payload<<{delimiter}\n{serialized}\n{delimiter}\n"

    def run(self) -> None:
        """Build the payload and write it to ``$GITHUB_OUTPUT``.

        Falls back to ``stdout`` when ``GITHUB_OUTPUT`` is unset (e.g.
        when invoked outside of a GitHub Actions runner for local
        debugging).
        """
        payload: dict = self.build_payload()
        line: str = self.format_github_output(payload)
        github_output: str | None = self._env.get("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a", encoding="utf-8") as fh:
                fh.write(line)
        else:
            sys.stdout.write(line)

    @staticmethod
    def main() -> None:
        """Entry point."""
        SlackPayloadBuilder(os.environ).run()


if __name__ == "__main__":
    SlackPayloadBuilder.main()
