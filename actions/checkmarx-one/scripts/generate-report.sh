#!/usr/bin/env bash
set -euo pipefail

# Authenticate with Checkmarx One and download the scan report
# as checkmarx-report.pdf in the current working directory.
#
# Required environment variables:
#   CX_BASE_URI      - Checkmarx One portal URL
#   CX_TENANT        - Checkmarx One tenant name
#   CX_CLIENT_ID     - OAuth client ID
#   CX_CLIENT_SECRET - OAuth client secret
#   SCAN_ID          - Checkmarx scan ID
#
# Optional environment variables:
#   CX_IAM_URI       - IAM endpoint (derived from CX_BASE_URI
#                       when empty)

API_BASE="${CX_BASE_URI%/}"

# Use CX_IAM_URI if set, otherwise derive from CX_BASE_URI
# (e.g. https://us.ast.checkmarx.net -> https://us.iam.checkmarx.net)
if [[ -n "${CX_IAM_URI:-}" ]]; then
  IAM_URI="${CX_IAM_URI%/}"
else
  IAM_URI="${API_BASE/ast.checkmarx/iam.checkmarx}"
fi

echo "Authenticating with Checkmarx One at ${IAM_URI}"
AUTH_RESPONSE="$(curl --silent --show-error \
  --request POST \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=${CX_CLIENT_ID}" \
  --data-urlencode "client_secret=${CX_CLIENT_SECRET}" \
  "${IAM_URI}/auth/realms/${CX_TENANT}/protocol/openid-connect/token")"

TOKEN="$(echo "$AUTH_RESPONSE" \
  | jq --raw-output '.access_token' 2>/dev/null || true)"
if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo "::error::Failed to authenticate." \
    "Response: ${AUTH_RESPONSE}"
  exit 1
fi

# ── Fetch scan details to obtain project ID ─────────
echo "Fetching scan details for ${SCAN_ID}"
SCAN_RESPONSE="$(curl --silent --show-error \
  --header "Authorization: Bearer ${TOKEN}" \
  "${API_BASE}/api/scans/${SCAN_ID}")"
echo "Scan response: ${SCAN_RESPONSE}" \
  | head --lines=1 | head --bytes=500 || true

PROJECT_ID="$(echo "$SCAN_RESPONSE" \
  | jq --raw-output '.projectId // .projectID // empty' \
  2>/dev/null || true)"
if [[ -z "$PROJECT_ID" ]]; then
  echo "::warning::Could not extract projectId from scan"
else
  echo "Project ID: ${PROJECT_ID}"
fi

# ── Request report generation ───────────────────────
if [[ -n "$PROJECT_ID" ]]; then
  REPORT_BODY="$(jq --null-input \
    --arg scanId "$SCAN_ID" \
    --arg projectId "$PROJECT_ID" \
    '{
      reportType: "cli",
      reportName: "improved-scan-report",
      fileFormat: "pdf",
      data: {scanId: $scanId, projectId: $projectId}
    }')"
else
  REPORT_BODY="$(jq --null-input \
    --arg scanId "$SCAN_ID" \
    '{
      reportType: "cli",
      reportName: "improved-scan-report",
      fileFormat: "pdf",
      data: {scanId: $scanId}
    }')"
fi

echo "Requesting report for scan ${SCAN_ID}"
REPORT_RESPONSE="$(curl --silent --show-error \
  --write-out "\n%{http_code}" \
  --request POST \
  --header "Authorization: Bearer ${TOKEN}" \
  --header "Content-Type: application/json" \
  --data "$REPORT_BODY" \
  "${API_BASE}/api/reports")"

HTTP_CODE="$(echo "$REPORT_RESPONSE" | tail --lines=1)"
REPORT_BODY_RESP="$(echo "$REPORT_RESPONSE" | sed '$d')"
echo "Report API response (HTTP ${HTTP_CODE}):" \
  "${REPORT_BODY_RESP}"

if [[ "$HTTP_CODE" -ge 400 ]]; then
  echo "::error::Report creation failed" \
    "(HTTP ${HTTP_CODE}): ${REPORT_BODY_RESP}"
  exit 1
fi

REPORT_ID="$(echo "$REPORT_BODY_RESP" \
  | jq --raw-output '.reportId')"
if [[ -z "$REPORT_ID" || "$REPORT_ID" == "null" ]]; then
  echo "::error::No reportId in response:" \
    "${REPORT_BODY_RESP}"
  exit 1
fi

# ── Poll for report completion ──────────────────────
echo "Report ID: ${REPORT_ID} — polling for completion"
STATUS="unknown"
for i in $(seq 1 30); do
  STATUS_RESP="$(curl --silent --show-error \
    --header "Authorization: Bearer ${TOKEN}" \
    "${API_BASE}/api/reports/${REPORT_ID}")"

  echo "  Attempt ${i}/30 raw response: ${STATUS_RESP}"

  # Try common field names for status
  STATUS="$(echo "$STATUS_RESP" \
    | jq --raw-output '
        if type == "object" then
          (.status // .reportStatus // "unknown")
        else
          tostring
        end
      ' 2>/dev/null || echo "parse-error")"

  STATUS_LOWER="$(echo "$STATUS" | tr '[:upper:]' '[:lower:]')"
  echo "  Parsed status: ${STATUS_LOWER}"

  if [[ "$STATUS_LOWER" == "completed" ]]; then
    break
  elif [[ "$STATUS_LOWER" == "failed" ]]; then
    echo "::error::Report generation failed: ${STATUS_RESP}"
    exit 1
  fi

  sleep 10
done

if [[ "$STATUS_LOWER" != "completed" ]]; then
  echo "::error::Report generation timed out after 5 minutes"
  exit 1
fi

# ── Download the PDF ────────────────────────────────
DOWNLOAD_URL="$(echo "$STATUS_RESP" \
  | jq --raw-output '.url // empty' 2>/dev/null || true)"
if [[ -z "$DOWNLOAD_URL" ]]; then
  DOWNLOAD_URL="${API_BASE}/api/reports/${REPORT_ID}/download"
fi

echo "Downloading report from ${DOWNLOAD_URL}"
curl --silent --show-error --fail \
  --header "Authorization: Bearer ${TOKEN}" \
  --output "checkmarx-report.pdf" \
  "$DOWNLOAD_URL"

echo "Report downloaded successfully"
ls -la checkmarx-report.pdf
