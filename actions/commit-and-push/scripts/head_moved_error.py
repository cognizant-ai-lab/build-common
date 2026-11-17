"""head_moved_error.py

Defines the error ``commit_via_api.py`` raises when the branch moves.
"""


class HeadMovedError(Exception):
    """The branch head on GitHub is no longer ``expectedHeadOid``."""
