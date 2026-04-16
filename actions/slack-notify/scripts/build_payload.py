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


# Maps a job-status string to (slack emoji name, attachment color,
# human-readable status text).  Unknown statuses fall back to a
# neutral grey question mark and render the status verbatim.
STATUS_MAP = {
    "success": ("white_check_mark", "good", "Passed"),
    "failure": ("x", "danger", "Failed"),
    "cancelled": ("warning", "warning", "Cancelled"),
}


def build_payload(env: Mapping[str, str]) -> dict:
    """Return the Slack webhook payload dict built from ``env``.

    ``env`` is a mapping of the input environment variables set by
    ``action.yml`` (``INPUT_STATUS``, ``INPUT_MESSAGE``,
    ``INPUT_MENTION``, ``GH_REPO``, ``GH_REF``, ``GH_SERVER``,
    ``GH_RUN_ID``, ``GH_WORKFLOW``, ``GH_ACTOR``).
    """
    status = env["INPUT_STATUS"]
    emoji, color, status_text = STATUS_MAP.get(
        status,
        ("grey_question", "#808080", status),
    )

    message = env.get("INPUT_MESSAGE") or status_text

    mention = ""
    if status == "failure" and env.get("INPUT_MENTION") == "true":
        mention = "<!channel> "

    repo = env["GH_REPO"]
    ref = env["GH_REF"]
    run_url = f"{env['GH_SERVER']}/{repo}/actions/runs/{env['GH_RUN_ID']}"
    workflow = env["GH_WORKFLOW"]
    actor = env["GH_ACTOR"]

    section_text = (
        f"{mention}:{emoji}: *{message}* for "
        f"`{repo}` on `{ref}`\n"
        f"<{run_url}|View build run>"
    )
    context_text = f"Workflow: {workflow} | Triggered by: {actor}"

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


def _format_github_output(payload: dict) -> str:
    """Return the ``payload=<json>`` multiline block for GITHUB_OUTPUT.

    Uses the standard ``<<DELIMITER ... DELIMITER`` heredoc form so the
    serialized JSON can safely contain newlines (``json.dumps`` does
    not produce newlines by default, but the heredoc form matches the
    original bash implementation and keeps the contract stable).
    """
    serialized = json.dumps(payload)
    return f"payload<<PAYLOAD_EOF\n{serialized}\nPAYLOAD_EOF\n"


def main() -> None:
    payload = build_payload(os.environ)
    line = _format_github_output(payload)
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(line)
    else:
        sys.stdout.write(line)


if __name__ == "__main__":
    main()
