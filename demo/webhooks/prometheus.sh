#!/usr/bin/env bash
# Prometheus AlertManager → demo incident (scenario=demo, 2026-06-16 09:00-10:00).
set -euo pipefail
cd "$(dirname "$0")"; source ./_send.sh
send prometheus '{
  "status": "firing",
  "alerts": [{
    "labels": {"service": "payment-gateway", "scenario": "demo", "severity": "critical", "alertname": "HighErrorRate"},
    "annotations": {"summary": "payment-gateway: error rate spiked, TimeoutException dominant, p99 ~9x baseline"},
    "startsAt": "2026-06-16T09:10:00Z"
  }]
}'
