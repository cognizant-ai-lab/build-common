#!/usr/bin/env bash
# Downloads and installs a pinned version of actionlint using the official
# install script from the rhysd/actionlint GitHub repository.
# The version is passed as the first argument and is expected to come from
# the ACTIONLINT_VERSION GitHub repository variable (vars.ACTIONLINT_VERSION).
set -euo pipefail

VERSION="${1:?Usage: install-actionlint.sh <version>}"

URL="https://raw.githubusercontent.com"
URL="${URL}/rhysd/actionlint/main"
URL="${URL}/scripts/download-actionlint.bash"

bash <(curl --silent --show-error --location "$URL") "$VERSION"
pwd >> "$GITHUB_PATH"
