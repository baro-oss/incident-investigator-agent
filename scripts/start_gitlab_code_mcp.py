#!/usr/bin/env python3
"""Start MCP GitLab Code Server on port 9002.

Đọc source code qua GitLab REST API v4 (READ-ONLY).
Cần env GITLAB_TOKEN (read_api). Optional GITLAB_API_BASE (mặc định gitlab.com).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP GitLab Code Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9002)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).parent.parent))
    uvicorn.run(
        "mcp_server.server_gitlab_code:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
