"""head_moved_error.py

Defines the error ``commit_via_api.py`` raises when the branch moves.
"""

from api_commit_error import ApiCommitError


class HeadMovedError(ApiCommitError):
    """The branch head on GitHub is no longer ``expectedHeadOid``."""
