"""Shared utilities for intake adapters."""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime
from typing import Tuple


def parse_alert_time(iso_str: str) -> Tuple[str, str]:
    """
    Parse ISO 8601 timestamp → (time_window "HH:00-(HH+1):00", date "YYYY-MM-DD").
    time_window floor đến giờ, +1 giờ — match với window synthetic data.
    Fallback về ("14:00-15:00", "2024-01-15") nếu parse lỗi.
    """
    try:
        iso = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        date_str = dt.strftime("%Y-%m-%d")
        h = dt.hour
        time_window = f"{h:02d}:00-{(h + 1) % 24:02d}:00"
        return time_window, date_str
    except (ValueError, AttributeError, TypeError):
        return "14:00-15:00", "2024-01-15"


def verify_webhook_signature(source: str, raw_body: bytes, headers: dict) -> bool:
    """
    Verify HMAC-SHA256 chữ ký webhook.

    Trả True nếu:
    - Env secret không được set → pass-through (backward compat)
    - Secret đúng

    Trả False nếu secret đã set nhưng chữ ký sai hoặc thiếu header.

    Prometheus/Grafana/alertmanager:
        Env: PROMETHEUS_WEBHOOK_SECRET / GRAFANA_WEBHOOK_SECRET
        Header: X-Webhook-Secret = HMAC-SHA256(body, secret) hex

    Sentry:
        Env: SENTRY_WEBHOOK_SECRET
        Header: sentry-hook-signature = sha256=HMAC-SHA256(body, secret) hex
    """
    src = source.lower().strip()

    if src in ("prometheus", "alertmanager", "grafana"):
        env_var = f"{src.upper()}_WEBHOOK_SECRET"
        secret = os.getenv(env_var)
        if not secret:
            return True  # pass-through — không set secret thì không enforce
        header_val = headers.get("x-webhook-secret", "")
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(header_val.lower(), expected.lower())

    elif src == "sentry":
        secret = os.getenv("SENTRY_WEBHOOK_SECRET")
        if not secret:
            return True
        header_val = headers.get("sentry-hook-signature", "")
        # Sentry gửi "sha256=<hexdigest>" hoặc bare hexdigest
        if header_val.startswith("sha256="):
            header_val = header_val[7:]
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(header_val.lower(), expected.lower())

    return True  # source không biết → pass-through
