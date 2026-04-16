#!/usr/bin/env bash
# Send a text message to a Feishu user via open_id.
# Requires env: FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_TARGET_OPEN_ID, FEISHU_TEXT.
# If app credentials are missing, skip silently (exit 0) so CI still passes.
set -euo pipefail

if [ -z "${FEISHU_APP_ID:-}" ] || [ -z "${FEISHU_APP_SECRET:-}" ]; then
  echo "[notify-feishu] skip: FEISHU_APP_ID/SECRET not configured"
  exit 0
fi

OPEN_ID="${FEISHU_TARGET_OPEN_ID:?FEISHU_TARGET_OPEN_ID required}"
TEXT="${FEISHU_TEXT:?FEISHU_TEXT required}"

token_resp=$(curl -sS -X POST \
  "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d "$(jq -n --arg id "$FEISHU_APP_ID" --arg sec "$FEISHU_APP_SECRET" \
        '{app_id: $id, app_secret: $sec}')")

token=$(printf '%s' "$token_resp" | jq -r '.tenant_access_token // empty')
if [ -z "$token" ]; then
  echo "[notify-feishu] failed to get tenant_access_token: $token_resp" >&2
  exit 1
fi

# Feishu requires the `content` field to be a JSON-encoded string.
content_str=$(jq -n --arg t "$TEXT" '{text: $t} | tostring')
payload=$(jq -n \
  --arg rid "$OPEN_ID" \
  --arg mt "text" \
  --arg c "$content_str" \
  '{receive_id: $rid, msg_type: $mt, content: $c}')

resp=$(curl -sS -X POST \
  "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id" \
  -H "Authorization: Bearer $token" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d "$payload")

code=$(printf '%s' "$resp" | jq -r '.code // -1')
if [ "$code" != "0" ]; then
  echo "[notify-feishu] send failed: $resp" >&2
  exit 1
fi
echo "[notify-feishu] sent ok"
