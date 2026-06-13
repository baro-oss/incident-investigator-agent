"""Shared utilities for intake adapters."""
from __future__ import annotations

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
