#!/usr/bin/env bash
# OpsGenie alert → demo incident (scenario qua details.scenario).
# createdAt = epoch ms của 2026-06-16T09:14:00Z = 1781601240000
set -euo pipefail
cd "$(dirname "$0")"; source ./_send.sh
send opsgenie '{
  "action": "Create",
  "alert": {
    "alertId": "demo-abc123",
    "message": "High error rate on payment-gateway (deploy correlated)",
    "alias": "payment-gateway-high-error",
    "source": "payment-gateway",
    "tags": ["critical"],
    "details": {"service": "payment-gateway", "scenario": "demo"},
    "createdAt": 1781601240000
  },
  "source": {"name": "payment-gateway"}
}'
