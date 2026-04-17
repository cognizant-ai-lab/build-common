"""Tests for the slack-notify ``build_payload`` script.

These exercise the payload builder in isolation -- no network, no
GitHub Actions runtime required -- so they can run as part of the
standard pytest step in CI.  ``conftest.py`` in this directory puts
the sibling ``scripts/`` directory on ``sys.path`` so the module can
be imported with a plain ``import`` statement.
"""

from __future__ import annotations

import json
import logging

from build_payload import SlackPayloadBuilder


class TestBuildPayload:
    """Tests for the ``SlackPayloadBuilder`` class."""

    BASE_ENV: dict = {
        "GH_REPO": "cognizant-ai-lab/example",
        "GH_REF": "main",
        "GH_SERVER": "https://github.com",
        "GH_RUN_ID": "42",
        "GH_WORKFLOW": "Quality Gate",
        "GH_ACTOR": "octocat",
        "INPUT_MESSAGE": "",
        "INPUT_MENTION": "false",
    }

    @classmethod
    def _env(cls, **overrides: str) -> dict:
        """Return a copy of ``BASE_ENV`` with ``overrides`` applied."""
        env = dict(cls.BASE_ENV)
        env.update(overrides)
        return env

    @staticmethod
    def _dig(obj: object, *path: object) -> object:
        """Walk a nested dict/list path without using ``[]`` on dicts.

        String ``path`` elements are looked up as dict keys via
        ``Mapping.get`` (per the repo's hard rule against ``[]`` dict
        access); integer elements are used as list indices.  Returns
        ``None`` as soon as any step is missing, so assertions that
        expect a specific value will fail with a clear
        ``AssertionError`` instead of a structure-dependent
        ``KeyError``/``IndexError``.
        """
        for step in path:
            if obj is None:
                return None
            if isinstance(step, str) and isinstance(obj, dict):
                obj = obj.get(step)
            elif isinstance(step, int) and isinstance(obj, list):
                obj = obj[step] if 0 <= step < len(obj) else None
            else:
                return None
        return obj

    @classmethod
    def _section_text(cls, payload: dict) -> object:
        """Return the markdown text of the payload's section block."""
        return cls._dig(
            payload,
            "attachments",
            0,
            "blocks",
            0,
            "text",
            "text",
        )

    @classmethod
    def _context_text(cls, payload: dict) -> object:
        """Return the markdown text of the payload's context block."""
        return cls._dig(
            payload,
            "attachments",
            0,
            "blocks",
            1,
            "elements",
            0,
            "text",
        )

    @classmethod
    def _color(cls, payload: dict) -> object:
        """Return the attachment color for the payload."""
        return cls._dig(payload, "attachments", 0, "color")

    def test_success_payload_shape(self) -> None:
        payload = SlackPayloadBuilder(
            self._env(INPUT_STATUS="success"),
        ).build_payload()

        assert self._color(payload) == "good"

        section = self._section_text(payload)
        assert ":white_check_mark:" in section
        assert "*Passed*" in section
        assert "`cognizant-ai-lab/example`" in section
        assert "`main`" in section
        assert (
            "<https://github.com/cognizant-ai-lab/example/actions/runs/42"
            "|View build run>"
        ) in section

        assert self._context_text(payload) == (
            "Workflow: Quality Gate | Triggered by: octocat"
        )

    def test_failure_with_mention_prepends_channel(self) -> None:
        payload = SlackPayloadBuilder(
            self._env(INPUT_STATUS="failure", INPUT_MENTION="true"),
        ).build_payload()

        assert self._color(payload) == "danger"
        section = self._section_text(payload)
        assert section.startswith("<!channel> :x:")
        assert "*Failed*" in section

    def test_failure_without_mention_has_no_channel_prefix(self) -> None:
        payload = SlackPayloadBuilder(
            self._env(INPUT_STATUS="failure", INPUT_MENTION="false"),
        ).build_payload()

        section = self._section_text(payload)
        assert not section.startswith("<!channel>")
        assert ":x:" in section

    def test_cancelled_payload_uses_warning_styling(self) -> None:
        payload = SlackPayloadBuilder(
            self._env(INPUT_STATUS="cancelled"),
        ).build_payload()

        assert self._color(payload) == "warning"
        section = self._section_text(payload)
        assert ":warning:" in section
        assert "*Cancelled*" in section

    def test_unknown_status_falls_through_to_neutral_styling(self, caplog) -> None:
        with caplog.at_level(logging.WARNING):
            payload = SlackPayloadBuilder(
                self._env(INPUT_STATUS="mystery"),
            ).build_payload()

        assert self._color(payload) == "#808080"
        section = self._section_text(payload)
        assert ":grey_question:" in section
        assert "*mystery*" in section

    def test_unknown_status_logs_actionable_warning(self, caplog) -> None:
        """An unknown status must emit a WARNING the operator can act on.

        Rendering verbatim is graceful degradation, but a Slack card
        with a grey_question icon is easy to miss.  The WARNING gives
        the CI-log reader a grep-able, actionable signal that the
        caller's ``status:`` input doesn't match any mapped value.
        """
        with caplog.at_level(logging.WARNING):
            SlackPayloadBuilder(
                self._env(INPUT_STATUS="mystery"),
            ).build_payload()

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert "mystery" in message
        assert "status" in message.lower()

    def test_known_status_does_not_log_a_warning(self, caplog) -> None:
        """Mapped statuses must not trigger the unknown-status warning."""
        with caplog.at_level(logging.WARNING):
            SlackPayloadBuilder(
                self._env(INPUT_STATUS="success"),
            ).build_payload()

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert warnings == []

    def test_custom_message_overrides_status_text(self) -> None:
        payload = SlackPayloadBuilder(
            self._env(INPUT_STATUS="success", INPUT_MESSAGE="All green"),
        ).build_payload()

        section = self._section_text(payload)
        assert "*All green*" in section
        assert "*Passed*" not in section

    def test_mention_is_ignored_on_success(self) -> None:
        payload = SlackPayloadBuilder(
            self._env(INPUT_STATUS="success", INPUT_MENTION="true"),
        ).build_payload()

        section = self._section_text(payload)
        assert not section.startswith("<!channel>")

    def test_payload_is_json_round_trippable_with_special_characters(self) -> None:
        """Strings with quotes/backslashes survive a JSON round-trip.

        This is the guarantee that previously relied on ``jq --arg``; it
        now comes from ``json.dumps`` in the stdlib.  If anyone reverts
        to string concatenation without proper escaping, this test will
        fail.
        """
        payload = SlackPayloadBuilder(
            self._env(
                INPUT_STATUS="success",
                INPUT_MESSAGE='Quoted "stuff" and \\ backslashes',
            ),
        ).build_payload()

        assert json.loads(json.dumps(payload)) == payload

    def test_run_writes_heredoc_payload_to_github_output(self, tmp_path) -> None:
        """End-to-end: ``run()`` writes the heredoc-wrapped JSON payload.

        This exercises the contract the action actually relies on --
        ``main()`` calls ``run()``, which opens the file named by
        ``$GITHUB_OUTPUT`` in append mode and writes exactly one
        ``payload<<DELIM ... DELIM`` block containing the JSON-serialized
        payload.  Testing through ``run()`` (instead of reaching into
        ``format_github_output`` directly) keeps the test coupled to the
        public surface; the internal helper can be refactored or
        inlined without touching the test.
        """
        github_output = tmp_path / "github_output"
        builder = SlackPayloadBuilder(
            self._env(
                INPUT_STATUS="success",
                GITHUB_OUTPUT=str(github_output),
            ),
        )

        builder.run()

        contents = github_output.read_text(encoding="utf-8")
        assert contents.startswith("payload<<PAYLOAD_EOF\n")
        assert contents.endswith("PAYLOAD_EOF\n")

        # The middle line must be a single-line JSON object that
        # round-trips cleanly and matches what build_payload produces.
        middle = contents.split("\n", 1)[1].rsplit("\nPAYLOAD_EOF\n", 1)[0]
        assert json.loads(middle) == builder.build_payload()

    def test_run_logs_payload_when_github_output_unset(self, caplog) -> None:
        """Local-debug path: with ``$GITHUB_OUTPUT`` unset, the payload
        is emitted as an ``INFO`` log line on ``self._logger`` rather
        than written to stdout.  Matches the ``_logger``-everywhere
        pattern used by the sibling manifest scripts.
        """
        env = self._env(INPUT_STATUS="success")
        env.pop("GITHUB_OUTPUT", None)
        builder = SlackPayloadBuilder(env)

        with caplog.at_level(logging.INFO):
            builder.run()

        info_records = [r for r in caplog.records if r.levelname == "INFO"]
        assert len(info_records) == 1
        message = info_records[0].getMessage()
        assert "GITHUB_OUTPUT" in message
        assert "payload<<PAYLOAD_EOF" in message
        assert "PAYLOAD_EOF" in message.rsplit("\n", 1)[-1]
