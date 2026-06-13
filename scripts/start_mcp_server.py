"""
Wrapper khởi động MCP Tool Server.

Dùng: python scripts/start_mcp_server.py [--port 9000] [--reload]
"""
import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))           # for mcp_server.*
sys.path.insert(0, str(_ROOT / "src"))   # for agent.*

import uvicorn
from dotenv import load_dotenv
load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="Start MCP Tool Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()

    from mcp_server.server import app

    print(f"Starting MCP Tool Server on http://{args.host}:{args.port}/mcp")
    print("POST /mcp    — MCP JSON-RPC 2.0 (initialize / tools/list / tools/call)")
    print("GET  /health — tool list")
    print()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
