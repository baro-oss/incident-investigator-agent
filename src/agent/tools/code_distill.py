"""
Code distillation wrapper — Nguyên tắc #1.

Nhận raw text từ external MCP (diff / file content / blame / search),
trả Observation đã chưng cất. LLM không bao giờ thấy raw dump.

Risk heuristics là GENERIC (không keyword miền):
  - config-knob: số thay đổi sau pool/timeout/retry/limit/max/min/size
  - dep-bump: version token thay đổi trong manifest file
  - large-delete: deletions >> additions
  - removed-error-handling: try/except/catch biến mất
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from agent.tools.contracts import SAMPLES_HARD_CAP, Observation

# ── Risk heuristics (generic — không keyword miền) ───────────────────────────

# Keyword config-knob: khớp ngay cả khi là phần của compound (max_pool, retry_limit, ...)
_CONFIG_KNOB_KW = re.compile(
    r"pool|timeout|retry|limit|max|min|size|concurren|worker|thread|connection|backlog|queue|buf",
    re.IGNORECASE,
)
_HAS_NUMBER = re.compile(r"\d+")
_REMOVED_GUARD_RE = re.compile(
    r"^-.*\b(try|except|catch|finally|rescue|raise|throw|error_handler|on_error)\b",
    re.IGNORECASE | re.MULTILINE,
)
_VERSION_LINE_RE = re.compile(
    r'^[-+].*?["\']?([a-zA-Z][\w.-]+)["\']?\s*(?:[=]{1,3}|>=|<=|~=|\^)\s*["\']?(\d[\d.*+\-a-zA-Z]*)["\']?',
    re.MULTILINE,
)


def _detect_risk_signals(text: str) -> List[str]:
    """Trả list tín hiệu rủi ro tìm được. Generic — không keyword miền."""
    signals: List[str] = []

    # 1. Config-knob thay đổi — dò từng dòng diff (+/-)
    knob_hits: List[str] = []
    for line in text.splitlines():
        if not line or line[0] not in "+-":
            continue
        kw_m = _CONFIG_KNOB_KW.search(line)
        num_m = _HAS_NUMBER.search(line)
        if kw_m and num_m:
            knob_hits.append(f"{kw_m.group(0)}→{num_m.group(0)}")
    if knob_hits:
        signals.append(f"config-knob changed: {', '.join(knob_hits[:3])}")

    # 2. Xóa lớn so với thêm
    additions = len(re.findall(r"^\+(?!\+\+)", text, re.MULTILINE))
    deletions = len(re.findall(r"^-(?!--)", text, re.MULTILINE))
    if deletions > 0 and additions < deletions * 0.3:
        signals.append(f"large-delete: -{deletions} lines vs +{additions} lines")

    # 3. Error handling bị xóa
    if _REMOVED_GUARD_RE.search(text):
        signals.append("removed-error-handling: guard/except lines deleted")

    # 4. Dependency bump (manifest files: requirements.txt, package.json, etc.)
    ver_matches = _VERSION_LINE_RE.findall(text)
    if ver_matches:
        bumps = [f"{pkg}=={ver}" for pkg, ver in ver_matches[:2]]
        signals.append(f"dep-bump: {', '.join(bumps)}")

    return signals


def _extract_hunks(text: str, cap: int = SAMPLES_HARD_CAP) -> Tuple[List[Dict[str, Any]], int]:
    """
    Chia diff/file thành hunk/đoạn đại diện.
    Trả (samples ≤ cap, tổng_hunk_thật).
    """
    # Thử parse hunks kiểu unified diff (@@ ... @@)
    hunk_pattern = re.compile(r"(@@[^@]*@@[^\n]*\n(?:[ +-][^\n]*\n?)*)", re.MULTILINE)
    hunks = hunk_pattern.findall(text)

    if hunks:
        total = len(hunks)
        samples = []
        for h in hunks[:cap]:
            lines = h.splitlines()
            header = lines[0] if lines else ""
            body = "\n".join(lines[1:6])  # tối đa 5 dòng body
            samples.append({"hunk": header.strip(), "preview": body[:300]})
        return samples, total

    # Fallback: chia theo đoạn văn (file content)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    total = len(paragraphs) if paragraphs else 1
    samples = [{"line": p[:200]} for p in paragraphs[:cap]]
    return samples, total


def _build_summary(
    tool_name: str,
    service: str,
    files_changed: int,
    additions: int,
    deletions: int,
    risk_signals: List[str],
) -> str:
    """Tạo summary tự diễn giải — phải mang signal, không phải số thô."""
    parts = [f"{tool_name} ({service}):"]
    if files_changed:
        parts.append(f"{files_changed} file(s) changed, +{additions}/−{deletions}")
    if risk_signals:
        parts.append("RISK: " + "; ".join(risk_signals))
    elif files_changed:
        parts.append("không phát hiện rủi ro rõ ràng")
    else:
        parts.append("không có thay đổi")
    return " ".join(parts)


def distill_code_response(
    raw: str,
    *,
    tool_name: str,
    service: str,
) -> Observation:
    """
    Chưng cất raw diff/file/search từ external MCP → Observation (Nguyên tắc #1).

    Args:
        raw: text thô từ MCP tool (diff, file content, blame, search result).
        tool_name: tên MCP tool đã gọi (ví dụ "get_diff", "read_file").
        service: service đang điều tra (dùng trong metadata).

    Returns:
        Observation đã chưng cất — summary mang signal, ≤5 samples, không raw dump.
    """
    if not raw or not raw.strip():
        return Observation(
            summary=f"{tool_name} ({service}): không có nội dung trả về",
            aggregates={"files_changed": 0, "additions": 0, "deletions": 0, "risk_signals": []},
            samples=[],
            total_count=0,
            truncated=False,
            metadata={"tool_name": tool_name, "service": service, "source": "code_mcp"},
        )

    # Đếm thêm/xóa dòng (unified diff format)
    additions = len(re.findall(r"^\+(?!\+\+)", raw, re.MULTILINE))
    deletions = len(re.findall(r"^-(?!--)", raw, re.MULTILINE))

    # Đếm file thay đổi (diff --git a/... b/... hoặc --- a/...)
    file_headers = re.findall(r"^diff --git|^---\s+\S", raw, re.MULTILINE)
    files_changed = len(file_headers) if file_headers else (1 if raw.strip() else 0)

    risk_signals = _detect_risk_signals(raw)
    samples, total_hunks = _extract_hunks(raw)

    summary = _build_summary(tool_name, service, files_changed, additions, deletions, risk_signals)

    return Observation(
        summary=summary,
        aggregates={
            "files_changed": files_changed,
            "additions": additions,
            "deletions": deletions,
            "risk_signals": risk_signals,
        },
        samples=samples,
        total_count=total_hunks,
        truncated=total_hunks > SAMPLES_HARD_CAP,
        metadata={"tool_name": tool_name, "service": service, "source": "code_mcp"},
    )
