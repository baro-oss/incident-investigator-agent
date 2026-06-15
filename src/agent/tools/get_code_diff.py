"""
get_code_diff — Tool đọc diff/file qua external MCP code repository.

Factory: `build_code_diff_tool(project_id, code_mcp_client=None) -> Tool`.
- code_mcp_client=None: repo đã cấu hình, chưa có external MCP → trả metadata (không crash).
- code_mcp_client given: gọi tool diff từ MCP, distill qua code_distill (Nguyên tắc #1).
- READ-ONLY hoàn toàn — chỉ đọc, không ghi.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from agent.tools.code_distill import distill_code_response
from agent.tools.contracts import Observation, Tool

if TYPE_CHECKING:
    from agent.tools.mcp_client import MCPClient

logger = logging.getLogger(__name__)

CODE_DIFF_TOOL_NAME = "get_code_diff"

# Tên tool MCP ưu tiên dùng để lấy diff (theo thứ tự)
_MCP_DIFF_TOOL_CANDIDATES = ("get_diff", "diff", "get_file_diff", "fetch_diff")


def build_code_diff_tool(
    project_id: str,
    code_mcp_client: "Optional[MCPClient]" = None,
) -> Tool:
    """
    Tạo tool get_code_diff scope theo project_id.

    Engine chỉ thấy Tool interface đồng nhất. code_mcp_client=None là
    chế độ "repo configured, đọc được khi có MCP" — không crash, trả metadata.
    """

    async def run(params: dict) -> Observation:
        service = (params.get("service") or "").strip()
        version = (params.get("version") or params.get("ref") or "").strip()
        path = (params.get("path") or "").strip()

        # Lookup repo mapping theo project
        repo = None
        try:
            from agent.intake.project_registry import get_service_repo
            repo = get_service_repo(project_id, service)
        except Exception as e:
            logger.warning("Không đọc được service_repos cho %s/%s: %s", project_id, service, e)

        if not repo:
            return Observation(
                summary=(
                    f"{CODE_DIFF_TOOL_NAME} ({service}@{version}): "
                    "chưa cấu hình repo mapping — "
                    "thêm trong Project → Repo/Source để kích hoạt đọc code."
                ),
                aggregates={"files_changed": 0, "risk_signals": [], "configured": False},
                samples=[],
                total_count=0,
                truncated=False,
                metadata={
                    "tool_name": CODE_DIFF_TOOL_NAME,
                    "service": service,
                    "version": version,
                    "source": "code_mcp",
                    "status": "no_repo_mapping",
                },
            )

        repo_url = repo["repo_url"]
        branch = version or repo.get("default_branch", "main")
        provider = repo.get("provider", "github")

        if code_mcp_client is None:
            return Observation(
                summary=(
                    f"{CODE_DIFF_TOOL_NAME} ({service}@{version or branch}): "
                    f"repo {repo_url} ({provider}) đã cấu hình, "
                    "chưa kết nối MCP — cấu hình GitHub/GitLab MCP để đọc diff."
                ),
                aggregates={
                    "files_changed": 0,
                    "risk_signals": [],
                    "repo_url": repo_url,
                    "ref": branch,
                    "configured": True,
                },
                samples=[],
                total_count=0,
                truncated=False,
                metadata={
                    "tool_name": CODE_DIFF_TOOL_NAME,
                    "service": service,
                    "version": version,
                    "repo_url": repo_url,
                    "source": "code_mcp",
                    "status": "no_mcp_client",
                },
            )

        # Có external MCP client — tìm tool diff và gọi
        try:
            mcp_tools = await code_mcp_client.get_tools()
            mcp_tool_map = {t.name: t for t in mcp_tools}

            diff_tool = None
            for candidate in _MCP_DIFF_TOOL_CANDIDATES:
                if candidate in mcp_tool_map:
                    diff_tool = mcp_tool_map[candidate]
                    break

            if diff_tool is None:
                return Observation(
                    summary=(
                        f"{CODE_DIFF_TOOL_NAME} ({service}@{version}): "
                        f"MCP server không có tool diff. Có: {list(mcp_tool_map)[:5]}"
                    ),
                    aggregates={"files_changed": 0, "risk_signals": []},
                    samples=[],
                    total_count=0,
                    truncated=False,
                    metadata={
                        "tool_name": CODE_DIFF_TOOL_NAME,
                        "service": service,
                        "source": "code_mcp",
                        "status": "no_diff_tool",
                    },
                )

            raw_obs: Observation = await diff_tool.run({
                "repo": repo_url,
                "ref": branch,
                "path": path,
            })
            raw_text = raw_obs.summary or ""
            return distill_code_response(raw_text, tool_name=CODE_DIFF_TOOL_NAME, service=service)

        except Exception as e:
            logger.error("Lỗi khi gọi code MCP cho %s@%s: %s", service, version, e)
            return Observation(
                summary=(
                    f"{CODE_DIFF_TOOL_NAME} ({service}@{version}): "
                    f"lỗi khi gọi code MCP — {type(e).__name__}: {e}"
                ),
                aggregates={"files_changed": 0, "risk_signals": [], "error": str(e)},
                samples=[],
                total_count=0,
                truncated=False,
                metadata={
                    "tool_name": CODE_DIFF_TOOL_NAME,
                    "service": service,
                    "version": version,
                    "source": "code_mcp",
                    "status": "mcp_error",
                },
            )

    return Tool(
        name=CODE_DIFF_TOOL_NAME,
        description=(
            "Đọc diff của version deploy nghi vấn qua external MCP code repository "
            "(GitHub/GitLab). Nhận service + version từ get_recent_deploys. "
            "Trả Observation chưng cất: risk signals (config-knob/dep-bump/removed-guard), "
            "files_changed, samples. READ-ONLY."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Tên service cần đọc code (phải khớp service_repos mapping)",
                },
                "version": {
                    "type": "string",
                    "description": "Version/tag/ref — thường lấy từ output của get_recent_deploys",
                },
                "path": {
                    "type": "string",
                    "description": "Path file/dir trong repo (tùy chọn, để trống = diff toàn bộ version)",
                },
            },
            "required": ["service", "version"],
        },
        run=run,
    )
