#!/usr/bin/env bash
# Grafana Unified Alerting → demo incident (scenario=demo).
set -euo pipefail
cd "$(dirname "$0")"; source ./_send.sh
send grafana '{
  "status": "firing",
  "title": "[FIRING:1] payment-gateway HighLatency",
  "message": "p99 latency vượt ngưỡng",
  "alerts": [{
    "labels": {"service": "payment-gateway", "scenario": "demo", "alertname": "HighLatency"},
    "annotations": {"summary": "payment-gateway: latency p99 lệch nghiêm trọng so với baseline"},
    "startsAt": "2026-06-16T09:12:00Z",
    "values": {"B0": 1080.5}
  }]
}'
