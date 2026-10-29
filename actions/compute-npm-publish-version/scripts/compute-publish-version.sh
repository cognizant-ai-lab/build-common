#!/usr/bin/env bash
#
# Computes the npm package version and dist-tag for a publish run.
#
# Environment:
#   EVENT_NAME:        GitHub event name (push, release, workflow_dispatch)
#   SHA:               Full Git SHA
#   RUN_NUMBER:        GitHub Actions run number
#   PACKAGE_JSON_PATH: package.json that holds the base version
#   RELEASE_TAG:       Release tag name (required for release events)
#   DIST_TAG_INPUT:    dist-tag for workflow_dispatch (default: prerelease)
#
# Version formats by trigger:
#   push:              <base>-main.<short_sha>.<run_number>, dist-tag "main"
#   release:           <release_tag> without a "v" prefix, dist-tag "latest"
#   workflow_dispatch: <base>-pr.<short_sha>.<run_number>, dist-tag from input
#
# <base> is the package.json version without any prerelease suffix.
# Writes version, dist_tag, sha and short_sha to $GITHUB_OUTPUT.

set -euo pipefail

EVENT_NAME="${EVENT_NAME:-}"
SHA="${SHA:-}"
RUN_NUMBER="${RUN_NUMBER:-}"
PACKAGE_JSON_PATH="${PACKAGE_JSON_PATH:-}"
RELEASE_TAG="${RELEASE_TAG:-}"
DIST_TAG_INPUT="${DIST_TAG_INPUT:-prerelease}"

if [[ -z "$EVENT_NAME" || -z "$SHA" || -z "$RUN_NUMBER" \
      || -z "$PACKAGE_JSON_PATH" ]]; then
    echo "::error::EVENT_NAME, SHA, RUN_NUMBER and PACKAGE_JSON_PATH" \
        "are required" >&2
    exit 1
fi

if [[ ! -f "$PACKAGE_JSON_PATH" ]]; then
    echo "::error::package.json not found at $PACKAGE_JSON_PATH" >&2
    exit 1
fi

SHORT_SHA="${SHA:0:7}"

BASE_VERSION=$(jq -er '.version' "$PACKAGE_JSON_PATH")
BASE_VERSION="${BASE_VERSION%%-*}"

if [[ "$EVENT_NAME" == "push" ]]; then
    VERSION="${BASE_VERSION}-main.${SHORT_SHA}.${RUN_NUMBER}"
    DIST_TAG="main"
    echo "Publishing merge snapshot: $VERSION with dist-tag: $DIST_TAG"
elif [[ "$EVENT_NAME" == "release" ]]; then
    if [[ -z "$RELEASE_TAG" ]]; then
        echo "::error::RELEASE_TAG is required for release events" >&2
        exit 1
    fi
    VERSION="${RELEASE_TAG#v}"
    DIST_TAG="latest"
    echo "Publishing release version: $VERSION with dist-tag: $DIST_TAG"
else
    VERSION="${BASE_VERSION}-pr.${SHORT_SHA}.${RUN_NUMBER}"
    DIST_TAG="$DIST_TAG_INPUT"
    echo "Publishing manual version: $VERSION with dist-tag: $DIST_TAG"
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    {
        echo "version=$VERSION"
        echo "dist_tag=$DIST_TAG"
        echo "sha=$SHA"
        echo "short_sha=$SHORT_SHA"
    } >> "$GITHUB_OUTPUT"
fi

echo "Version: $VERSION"
echo "Dist-tag: $DIST_TAG"
echo "SHA: $SHA"
echo "Short SHA: $SHORT_SHA"
