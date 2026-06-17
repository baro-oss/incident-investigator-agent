#!/usr/bin/env bash
# Trigger thủ công demo2 (map_simple_payload) — đường chắc chắn nhất, mọi tham số tường minh.
# Không có X-Alert-Source → cần ALLOW_ANON_TRIGGER=true hoặc API_TOKEN.
set -euo pipefail
cd "$(dirname "$0")"; source ./_send.sh
send "" '{
  "service": "auth-service",
  "scenario": "demo2",
  "time_window": "14:00-15:00",
  "date": "2026-06-17",
  "symptom": "auth-service: HTTP_401 / AuthenticationError tăng đột biến sau deploy v1.2.0"
}'
