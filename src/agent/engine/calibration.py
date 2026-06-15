"""
E8: Calibration engine — đọc historical eval accuracy từ DB, điều chỉnh verdict confidence.

Đọc từ eval_results (lưu bởi eval_agent.py).
Hạ confidence nếu accuracy của tier đó < ngưỡng VÀ có đủ dữ liệu (≥5 runs).
Cache in-memory 5 phút để tránh DB query mỗi investigation.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from agent.engine.state import Verdict

logger = logging.getLogger(__name__)

# Ngưỡng accuracy; nếu tier thấp hơn → hạ 1 bậc
CALIBRATION_THRESHOLDS: Dict[str, float] = {
    "high": 0.80,
    "medium": 0.60,
    "low": 0.40,
}

# Số run tối thiểu per tier để kích hoạt calibration (tránh noise dữ liệu ít)
MIN_DATA_POINTS = 5

# Hạ 1 bậc
_DOWNGRADE: Dict[str, str] = {
    "high": "medium",
    "medium": "low",
    "low": "insufficient",
}

# Simple TTL cache
_cache: Optional[Dict] = None
_cache_ts: float = 0.0
_CACHE_TTL = 300.0  # 5 phút


def load_calibration_stats(db=None) -> Dict[str, Dict]:
    """
    Đọc eval_results từ DB.
    Trả: {tier: {"count": N, "correct": N, "accuracy": float}}
    Trả dict rỗng nếu bảng chưa có hoặc không có dữ liệu.
    """
    global _cache, _cache_ts
    now = time.monotonic()
    if _cache is not None and (now - _cache_ts) < _CACHE_TTL:
        return _cache

    close_after = db is None
    if db is None:
        try:
            from agent.storage.db import open_db
            db = open_db()
        except Exception as e:
            logger.debug("Calibration: không mở được DB — %s", e)
            return {}

    stats: Dict[str, Dict] = {}
    try:
        rows = db.execute(
            """
            SELECT confidence,
                   COUNT(*) AS total,
                   SUM(CASE WHEN correct = 1 THEN 1 ELSE 0 END) AS correct_count
            FROM eval_results
            WHERE confidence IN ('high', 'medium', 'low')
            GROUP BY confidence
            """
        ).fetchall()
        for row in rows:
            tier, total, correct = row[0], row[1], row[2] or 0
            stats[tier] = {
                "count": total,
                "correct": correct,
                "accuracy": correct / total if total > 0 else 0.0,
            }
    except Exception as e:
        logger.debug("Calibration: lỗi đọc eval_results — %s", e)
    finally:
        if close_after:
            try:
                db.close()
            except Exception:
                pass

    _cache = stats
    _cache_ts = now
    return stats


def get_calibration_adjustment(confidence: str, stats: Dict[str, Dict]) -> str:
    """
    Trả confidence đã điều chỉnh (có thể thấp hơn input).
    Hạ khi tier có đủ dữ liệu VÀ accuracy < ngưỡng.
    """
    if confidence not in CALIBRATION_THRESHOLDS:
        return confidence

    tier_stats = stats.get(confidence)
    if not tier_stats:
        return confidence  # không có dữ liệu → giữ nguyên

    if tier_stats["count"] < MIN_DATA_POINTS:
        return confidence  # chưa đủ dữ liệu

    threshold = CALIBRATION_THRESHOLDS[confidence]
    if tier_stats["accuracy"] < threshold:
        downgraded = _DOWNGRADE.get(confidence, confidence)
        logger.info(
            "Calibration: hạ %s → %s (accuracy=%.1f%% < threshold=%.0f%%)",
            confidence, downgraded,
            tier_stats["accuracy"] * 100, threshold * 100,
        )
        return downgraded

    return confidence


def apply_calibration(verdict: "Verdict", stats: Dict[str, Dict] = None) -> "Verdict":
    """
    Áp dụng calibration lên verdict.
    Đặt calibrated_confidence khi có điều chỉnh; None nếu không thay đổi.
    stats=None → tự load từ DB.
    """
    if stats is None:
        stats = load_calibration_stats()

    if not stats:
        return verdict  # không có dữ liệu calibration → pass through

    original = verdict.confidence
    adjusted = get_calibration_adjustment(original, stats)

    if adjusted != original:
        verdict.calibrated_confidence = adjusted
        verdict.confidence = adjusted

    return verdict


def get_calibration_summary(stats: Dict[str, Dict] = None) -> list:
    """
    Trả list dict mô tả calibration status cho từng tier.
    Dùng để hiển thị trên dashboard (before/after).
    """
    if stats is None:
        stats = load_calibration_stats()

    result = []
    for tier in ("high", "medium", "low"):
        tier_stats = stats.get(tier, {})
        count = tier_stats.get("count", 0)
        accuracy = tier_stats.get("accuracy", None)
        threshold = CALIBRATION_THRESHOLDS[tier]
        adjustment = get_calibration_adjustment(tier, stats) if count >= MIN_DATA_POINTS else tier
        result.append({
            "tier": tier,
            "count": count,
            "accuracy_pct": round(accuracy * 100) if accuracy is not None else None,
            "threshold_pct": round(threshold * 100),
            "adjusted_to": adjustment if adjustment != tier else None,
            "has_data": count >= MIN_DATA_POINTS,
        })
    return result


def invalidate_cache() -> None:
    """Gọi sau khi ghi eval_results mới để buộc refresh calibration ở investigation kế tiếp."""
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0.0
