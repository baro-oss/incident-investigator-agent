#!/usr/bin/env bash
# Trigger thủ công (map_simple_payload) — đường chắc chắn nhất, mọi tham số tường minh.
# Không có X-Alert-Source → cần ALLOW_ANON_TRIGGER=true hoặc API_TOKEN.
set -euo pipefail
cd "$(dirname "$0")"; source ./_send.sh
send "" '{
  "service": "payment-gateway",
  "scenario": "demo",
  "time_window": "09:00-10:00",
  "date": "2026-06-16",
  "symptom": "payment-gateway: TimeoutException tăng đột biến sau deploy, p99 ~9x baseline"
}'
