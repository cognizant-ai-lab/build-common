"""Make ``build_payload.py`` directly importable by test modules.

``build_payload.py`` lives next to ``action.yml`` under
``actions/slack-notify/scripts/`` rather than in an installable
Python package.  The directory name ``slack-notify`` contains a
hyphen so it cannot itself be a Python package, but the sibling
``scripts/`` directory can be added to ``sys.path`` so tests can use
a plain ``from build_payload import SlackPayloadBuilder`` rather
than an ``importlib.util`` dance per test.

This file is auto-discovered by pytest before any test module in
this directory is imported.
"""

from __future__ import annotations

import pathlib
import sys


class _ScriptsPathInjector:
    """Adds the sibling ``scripts/`` directory to ``sys.path``."""

    SCRIPTS_DIR: pathlib.Path = (
        pathlib.Path(__file__).resolve().parent.parent / "scripts"
    )

    @classmethod
    def inject(cls) -> None:
        """Prepend ``SCRIPTS_DIR`` to ``sys.path`` if not already present."""
        scripts_path: str = str(cls.SCRIPTS_DIR)
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)


_ScriptsPathInjector.inject()
