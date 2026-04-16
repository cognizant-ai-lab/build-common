"""Tests for the slack-notify ``build_payload`` script.

These exercise the payload builder in isolation -- no network, no
GitHub Actions runtime required -- so they can run as part of the
standard pytest step in CI.  The script is loaded by file path
because it lives next to ``action.yml`` rather than in an importable
package.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
from types import ModuleType


SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "build_payload.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_payload",
        SCRIPT_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE_ENV = {
    "GH_REPO": "cognizant-ai-lab/example",
    "GH_REF": "main",
    "GH_SERVER": "https://github.com",
    "GH_RUN_ID": "42",
    "GH_WORKFLOW": "Quality Gate",
    "GH_ACTOR": "octocat",
    "INPUT_MESSAGE": "",
    "INPUT_MENTION": "false",
}


def _env(**overrides: str) -> dict:
    env = dict(BASE_ENV)
    env.update(overrides)
    return env


def _section_text(payload: dict) -> str:
    return payload["attachments"][0]["blocks"][0]["text"]["text"]


def _context_text(payload: dict) -> str:
    return payload["attachments"][0]["blocks"][1]["elements"][0]["text"]


def test_success_payload_shape():
    mod = _load_module()
    payload = mod.SlackPayloadBuilder(_env(INPUT_STATUS="success")).build_payload()

    attachment = payload["attachments"][0]
    assert attachment["color"] == "good"

    section = _section_text(payload)
    assert ":white_check_mark:" in section
    assert "*Passed*" in section
    assert "`cognizant-ai-lab/example`" in section
    assert "`main`" in section
    assert (
        "<https://github.com/cognizant-ai-lab/example/actions/runs/42|View build run>"
    ) in section

    assert _context_text(payload) == ("Workflow: Quality Gate | Triggered by: octocat")


def test_failure_with_mention_prepends_channel():
    mod = _load_module()
    payload = mod.SlackPayloadBuilder(
        _env(INPUT_STATUS="failure", INPUT_MENTION="true"),
    ).build_payload()

    assert payload["attachments"][0]["color"] == "danger"
    section = _section_text(payload)
    assert section.startswith("<!channel> :x:")
    assert "*Failed*" in section


def test_failure_without_mention_has_no_channel_prefix():
    mod = _load_module()
    payload = mod.SlackPayloadBuilder(
        _env(INPUT_STATUS="failure", INPUT_MENTION="false"),
    ).build_payload()

    section = _section_text(payload)
    assert not section.startswith("<!channel>")
    assert ":x:" in section


def test_cancelled_payload_uses_warning_styling():
    mod = _load_module()
    payload = mod.SlackPayloadBuilder(_env(INPUT_STATUS="cancelled")).build_payload()

    assert payload["attachments"][0]["color"] == "warning"
    section = _section_text(payload)
    assert ":warning:" in section
    assert "*Cancelled*" in section


def test_unknown_status_falls_through_to_neutral_styling():
    mod = _load_module()
    payload = mod.SlackPayloadBuilder(_env(INPUT_STATUS="mystery")).build_payload()

    assert payload["attachments"][0]["color"] == "#808080"
    section = _section_text(payload)
    assert ":grey_question:" in section
    assert "*mystery*" in section


def test_custom_message_overrides_status_text():
    mod = _load_module()
    payload = mod.SlackPayloadBuilder(
        _env(INPUT_STATUS="success", INPUT_MESSAGE="All green"),
    ).build_payload()

    section = _section_text(payload)
    assert "*All green*" in section
    assert "*Passed*" not in section


def test_mention_is_ignored_on_success():
    mod = _load_module()
    payload = mod.SlackPayloadBuilder(
        _env(INPUT_STATUS="success", INPUT_MENTION="true"),
    ).build_payload()

    section = _section_text(payload)
    assert not section.startswith("<!channel>")


def test_payload_is_json_round_trippable_with_special_characters():
    """Strings with quotes/backslashes survive a JSON round-trip.

    This is the guarantee that previously relied on ``jq --arg``; it
    now comes from ``json.dumps`` in the stdlib.  If anyone reverts
    to string concatenation without proper escaping, this test will
    fail.
    """
    mod = _load_module()
    payload = mod.SlackPayloadBuilder(
        _env(
            INPUT_STATUS="success",
            INPUT_MESSAGE='Quoted "stuff" and \\ backslashes',
        ),
    ).build_payload()

    assert json.loads(json.dumps(payload)) == payload


def test_format_github_output_wraps_payload_in_heredoc():
    mod = _load_module()
    builder = mod.SlackPayloadBuilder(_env(INPUT_STATUS="success"))
    payload = builder.build_payload()

    line = builder.format_github_output(payload)
    assert line.startswith("payload<<PAYLOAD_EOF\n")
    assert line.endswith("PAYLOAD_EOF\n")

    # The middle line must be a single-line JSON object that
    # round-trips cleanly.
    middle = line.split("\n", 1)[1].rsplit("\nPAYLOAD_EOF\n", 1)[0]
    assert json.loads(middle) == payload
