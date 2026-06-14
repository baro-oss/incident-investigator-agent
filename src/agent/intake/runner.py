"""
Async runner — nhận InvestigationRequest, chạy engine background, push output.

Nguyên tắc: intake ack ngay → background task điều tra → output router.
Mọi nhánh kết thúc đều push (telegram / teams / ...), không chết im lặng.
MCP servers được connect trước investigation, close sau khi xong.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, List, Optional, Set

from agent.engine.loop import InvestigationEngine
from agent.engine.multi_agent import MultiAgentEngine
from agent.engine.resilience import investigation_limiter
from agent.engine.state import InvestigationState
from agent.intake.normalizer import InvestigationRequest
from agent.llm.factory import create_llm_client
from agent.memory.patterns import get_warm_start_hint, save_pattern
from agent.output.router import push_verdict
from agent.tools.mcp_client import MCPClient
from agent.tools.registry import build_tool_registry, get_mcp_urls_from_env

logger = logging.getLogger(__name__)


def _get_mcp_servers_for_project(project_id: str) -> List[Dict[str, str]]:
    """
    Nguồn chính: DB mcp_servers WHERE project_id=? AND enabled=1
                 → trả list dict {url, auth_type, auth_config}.
    Nguồn bổ sung: env var MCP_SERVER_URLS (thêm nếu chưa có, auth=none).
    """
    try:
        from agent.intake.mcp_registry import get_enabled_servers
        db_servers = get_enabled_servers(project_id=project_id)
    except Exception as e:
        logger.warning("Không đọc được mcp_servers từ DB: %s", e)
        db_servers = []

    seen_urls = {s["url"] for s in db_servers}
    for url in get_mcp_urls_from_env():
        if url not in seen_urls:
            db_servers.append({"url": url, "auth_type": "none", "auth_config": "{}"})
            seen_urls.add(url)

    return db_servers


# backward compat alias (dùng trong các nơi chỉ cần URL)
def _get_mcp_urls_for_project(project_id: str) -> List[str]:
    return [s["url"] for s in _get_mcp_servers_for_project(project_id)]


def _get_project_services(project_id: str) -> List[str]:
    try:
        from agent.intake.project_registry import list_project_services
        return list_project_services(project_id)
    except Exception as e:
        logger.warning("Không đọc được project_services: %s", e)
        return []


# Dedup: tập hợp dedup_key của các phiên đang chạy
_active_investigations: Set[str] = set()


async def _connect_mcp_clients(servers: List[Dict[str, str]]) -> List[MCPClient]:
    """Connect đến tất cả MCP server với auth. Bỏ qua server không phản hồi (log warning)."""
    import json as _json
    clients: List[MCPClient] = []
    for s in servers:
        url = s["url"]
        auth_type = s.get("auth_type", "none")
        auth_config: Dict = {}
        try:
            auth_config = _json.loads(s.get("auth_config") or "{}")
        except Exception:
            pass
        client = MCPClient(url, auth_type=auth_type, auth_config=auth_config)
        try:
            await client.connect()
            clients.append(client)
        except Exception as e:
            logger.warning("Bỏ qua MCP server %s (không kết nối được): %s", url, e)
    return clients


async def _close_mcp_clients(clients: List[MCPClient]) -> None:
    for client in clients:
        try:
            await client.close()
        except Exception:
            pass


def _make_error_state(req: InvestigationRequest, stop_reason: str) -> InvestigationState:
    return InvestigationState(
        investigation_id=req.dedup_key,
        symptom=req.symptom,
        time_window=req.time_window,
        scenario=req.scenario,
        date=req.date,
        stop_reason=stop_reason,
        finished=True,
    )


async def run_investigation_background(
    req: InvestigationRequest,
    step_budget: int = 10,
) -> None:
    """
    Chạy một phiên điều tra end-to-end trong background.
    Tự push Telegram khi xong — dù thành công, timeout hay lỗi.
    """
    key = req.dedup_key

    if key in _active_investigations:
        logger.info("Dedup: bỏ qua trigger trùng (key=%s)", key)
        return

    _active_investigations.add(key)
    logger.info("Bắt đầu background investigation: %s | limiter=%s",
                key, investigation_limiter.status_dict())

    mcp_clients: List[MCPClient] = []
    state: Optional[InvestigationState] = None

    # ConcurrencyLimiter: block nếu đã có 3 phiên chạy, queue cho đến khi có slot
    async with investigation_limiter:
        try:
            project_id = req.project_id

            # Đọc services của project → gợi ý scope điều tra
            available_services = _get_project_services(project_id)
            if available_services:
                logger.info("[%s] Project services: %s", project_id, available_services)

            # Connect MCP servers của project (+ env var fallback)
            mcp_servers = _get_mcp_servers_for_project(project_id)
            if mcp_servers:
                mcp_urls = [s["url"] for s in mcp_servers]
                logger.info("[%s] Kết nối %d MCP server(s): %s", project_id, len(mcp_servers), mcp_urls)
                mcp_clients = await _connect_mcp_clients(mcp_servers)

            # Xây tool registry: fintech hoặc local + MCP
            if getattr(req, "domain", "microservice") == "fintech":
                from agent.tools.registry_fintech import get_fintech_tool_registry
                tools = get_fintech_tool_registry()
                logger.info("[%s] Dùng Fintech tool registry (%d tools)", key, len(tools))
            else:
                tools = await build_tool_registry(mcp_clients if mcp_clients else None)

            # Resolve LLM: project DB config → global env vars
            llm_cfg = None
            try:
                from agent.intake.project_registry import get_project_llm
                llm_cfg = get_project_llm(project_id)
            except Exception as e:
                logger.warning("Không đọc được project LLM config: %s", e)

            if llm_cfg:
                llm = create_llm_client(
                    provider=llm_cfg.get("provider"),
                    model=llm_cfg.get("model"),
                    extra_config=llm_cfg.get("config"),
                )
                logger.info("[%s] Dùng LLM từ project config: provider=%s model=%s",
                            project_id, llm_cfg.get("provider"), llm_cfg.get("model"))
            else:
                llm = create_llm_client()

            # Long-term memory: warm-start hint
            warm_hint = get_warm_start_hint(
                project_id=project_id,
                service=req.service,
                error_keywords=None,
            )
            if warm_hint:
                logger.info("[%s] Warm-start hint: %s", project_id, warm_hint[:80])

            # Chọn engine: MultiAgent (parallel) hoặc single-agent (LangGraph)
            if req.multi_agent:
                engine_obj = MultiAgentEngine(llm=llm, all_tools=tools, step_budget=step_budget)
                logger.info("[%s] Dùng MultiAgentEngine (parallel specialists)", key)
            else:
                engine_obj = InvestigationEngine(llm=llm, tools=tools, step_budget=step_budget)

            state = await asyncio.wait_for(
                engine_obj.run(
                    symptom=req.symptom,
                    time_window=req.time_window,
                    scenario=req.scenario,
                    date=req.date,
                    project_id=project_id,
                    available_services=available_services or None,
                    warm_start_hint=warm_hint,
                    investigation_id=key,
                ),
                timeout=300.0,
            )

        except asyncio.TimeoutError:
            logger.error("Investigation timeout sau 5 phút: %s", key)
            state = _make_error_state(req, "timeout")

        except Exception as e:
            logger.error("Investigation lỗi không mong đợi: %s — %s", key, e)
            state = _make_error_state(req, f"error: {e}")

        finally:
            _active_investigations.discard(key)
            await _close_mcp_clients(mcp_clients)

    # Long-term memory: lưu pattern nếu verdict HIGH
    if state and state.verdict and state.verdict.confidence == "high":
        try:
            save_pattern(state)
        except Exception as e:
            logger.warning("Không lưu được memory pattern: %s", e)

    # Push tất cả kênh output — luôn luôn, không chết im lặng
    await push_verdict(state)


def trigger_investigation(
    req: InvestigationRequest,
    step_budget: int = 10,
) -> asyncio.Task:
    """
    Fire-and-forget: tạo background task và trả ngay.
    Caller không cần await — điều tra chạy nền.
    """
    task = asyncio.create_task(
        run_investigation_background(req, step_budget=step_budget),
        name=f"investigation-{req.dedup_key}",
    )
    return task
