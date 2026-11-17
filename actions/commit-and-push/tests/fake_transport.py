"""fake_transport.py

Stands in for the GraphQL API in the ``commit_via_api`` tests.
"""

from __future__ import annotations


class FakeTransport:
    """Records GraphQL requests and replays canned replies."""

    def __init__(self, *replies: dict) -> None:
        """Store the replies to return, in order."""
        self.replies: list[dict] = list(replies)
        self.requests: list[dict] = []

    def __call__(self, body: dict) -> dict:
        """Record ``body`` and return the next reply."""
        self.requests.append(body.get("variables").get("input"))
        return self.replies.pop(0)
