"""api_commit_error.py

Defines the error ``commit_via_api.py`` raises when it cannot commit.
"""


class ApiCommitError(Exception):
    """The commit could not be made through the GitHub API."""
