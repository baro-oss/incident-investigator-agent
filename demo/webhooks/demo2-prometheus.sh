#!/usr/bin/env bash
# Prometheus AlertManager → demo2 incident (scenario=demo2, 2026-06-17 14:00-15:00).
set -euo pipefail
cd "$(dirname "$0")"; source ./_send.sh
send prometheus '{
  "status": "firing",
  "alerts": [{
    "labels": {"service": "auth-service", "scenario": "demo2", "severity": "critical", "alertname": "HighAuthErrorRate"},
    "annotations": {"summary": "auth-service: HTTP_401 spiked, AuthenticationError dominant, errors propagating to payment-gateway/api-gateway"},
    "startsAt": "2026-06-17T14:10:00Z"
  }]
}'
