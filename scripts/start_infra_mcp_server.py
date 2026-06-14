#!/usr/bin/env python3
"""Start MCP Infra Tool Server on port 9001."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP Infra Tool Server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).parent.parent))
    uvicorn.run(
        "mcp_server.server_infra:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
