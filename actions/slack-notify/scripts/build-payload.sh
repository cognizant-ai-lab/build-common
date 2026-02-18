#!/usr/bin/env bash
set -euo pipefail

case "$INPUT_STATUS" in
  success)
    EMOJI="white_check_mark"
    COLOR="good"
    STATUS_TEXT="Passed"
    ;;
  failure)
    EMOJI="x"
    COLOR="danger"
    STATUS_TEXT="Failed"
    ;;
  cancelled)
    EMOJI="warning"
    COLOR="warning"
    STATUS_TEXT="Cancelled"
    ;;
  *)
    EMOJI="grey_question"
    COLOR="#808080"
    STATUS_TEXT="$INPUT_STATUS"
    ;;
esac

if [ -n "$INPUT_MESSAGE" ]; then
  MESSAGE="$INPUT_MESSAGE"
else
  MESSAGE="$STATUS_TEXT"
fi

MENTION=""
if [ "$INPUT_STATUS" = "failure" ] && \
   [ "$INPUT_MENTION" = "true" ]; then
  MENTION="<!channel> "
fi

RUN_URL="${GH_SERVER}/${GH_REPO}"
RUN_URL="${RUN_URL}/actions/runs/${GH_RUN_ID}"

PAYLOAD=$(jq --null-input \
  --arg color "$COLOR" \
  --arg mention "$MENTION" \
  --arg emoji "$EMOJI" \
  --arg message "$MESSAGE" \
  --arg repo "$GH_REPO" \
  --arg ref "$GH_REF" \
  --arg run_url "$RUN_URL" \
  --arg workflow "$GH_WORKFLOW" \
  --arg actor "$GH_ACTOR" \
  '{
    "attachments": [
      {
        "color": $color,
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": (
                $mention + ":" + $emoji
                + ": *" + $message
                + "* for `" + $repo
                + "` on `" + $ref
                + "`\n<" + $run_url
                + "|View build run>"
              )
            }
          },
          {
            "type": "context",
            "elements": [
              {
                "type": "mrkdwn",
                "text": (
                  "Workflow: " + $workflow
                  + " | Triggered by: "
                  + $actor
                )
              }
            ]
          }
        ]
      }
    ]
  }')

echo "payload<<PAYLOAD_EOF" >> "$GITHUB_OUTPUT"
echo "$PAYLOAD" >> "$GITHUB_OUTPUT"
echo "PAYLOAD_EOF" >> "$GITHUB_OUTPUT"
