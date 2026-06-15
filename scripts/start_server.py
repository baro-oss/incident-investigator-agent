"""
Uvicorn wrapper — khởi động FastAPI investigation server.

Dùng: python scripts/start_server.py [--host 0.0.0.0] [--port 8080] [--reload]
Port mặc định: 8080 (AgentBase contract — KHÔNG đổi cho prod).
"""
import argparse
import os
import sys
from pathlib import Path

# Đảm bảo src/ trong path khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import uvicorn

from dotenv import load_dotenv
load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Investigation Agent webhook server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    parser.add_argument("--reload", action="store_true", help="Hot-reload khi code thay đổi (dev only)")
    args = parser.parse_args()

    print(f"Starting Investigation Agent server on http://{args.host}:{args.port}")
    print("POST /trigger  — kích điều tra mới")
    print("GET  /health   — kiểm tra server")
    print("GET  /docs     — Swagger UI")
    print()

    uvicorn.run(
        "agent.intake.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
