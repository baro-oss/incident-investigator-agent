#!/usr/bin/env bash
# Helper chung cho các script webhook demo.
#   source ./_send.sh ; send <x-alert-source|empty> <json-body>
# Env:
#   BASE        mặc định http://localhost:8080  (server chính chạy port 8080 từ Phase 11)
#   PROJECT_ID  mặc định demo-day
#   API_TOKEN   (tùy chọn) gửi kèm X-API-Token (nếu KHÔNG bật ALLOW_ANON_TRIGGER)
BASE="${BASE:-http://localhost:8080}"
PROJECT_ID="${PROJECT_ID:-demo-day}"

send() {
  local source="$1" body="$2"
  local url="$BASE/projects/$PROJECT_ID/trigger"
  local args=(-sS -X POST "$url" -H "Content-Type: application/json")
  [ -n "$source" ] && args+=(-H "X-Alert-Source: $source")
  [ -n "${API_TOKEN:-}" ] && args+=(-H "X-API-Token: $API_TOKEN")
  args+=(-d "$body")
  echo "→ POST $url  (source=${source:-none})"
  curl "${args[@]}"; echo
}
