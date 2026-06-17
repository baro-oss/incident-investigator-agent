#!/usr/bin/env bash
# PagerDuty incident.trigger → LƯU Ý: adapter PagerDuty SUY RA scenario từ title
# (chỉ scenario1/scenario2), KHÔNG mang được scenario=demo. Script này vì vậy
# nhắm vào scenario1 (data đã seed sẵn: payment-gateway v2.3.1 @ 2024-01-15) để
# chứng minh routing đa nền tảng. Code-diff sẽ KHÔNG kích hoạt (repo demo chỉ có
# tag v2.3.0/v2.4.0, không có v2.3.1). Dùng prometheus/grafana/sentry/opsgenie cho
# kịch bản demo chính (đọc code).
set -euo pipefail
cd "$(dirname "$0")"; source ./_send.sh
send pagerduty '{
  "messages": [{
    "event": "incident.trigger",
    "incident": {
      "id": "P1ABC23",
      "title": "High error rate after deploy on payment-gateway",
      "status": "triggered",
      "urgency": "high",
      "service": {"name": "payment-gateway", "id": "PSVC1"},
      "created_at": "2024-01-15T14:10:00Z"
    }
  }]
}'
