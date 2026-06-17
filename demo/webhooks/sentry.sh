#!/usr/bin/env bash
# Sentry Issue webhook → demo incident (scenario qua tags).
set -euo pipefail
cd "$(dirname "$0")"; source ./_send.sh
send sentry '{
  "action": "created",
  "data": {
    "issue": {
      "title": "TimeoutException: connection pool exhausted on payment-gateway",
      "firstSeen": "2026-06-16T09:08:00Z",
      "lastSeen": "2026-06-16T09:58:00Z",
      "project": {"slug": "payment-gateway", "name": "payment-gateway"},
      "metadata": {"type": "TimeoutException", "value": "upstream timed out after 30000ms"},
      "tags": [{"key": "scenario", "value": "demo"}]
    }
  }
}'
