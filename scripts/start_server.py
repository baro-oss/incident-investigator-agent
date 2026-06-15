"""
Uvicorn wrapper — khởi động FastAPI investigation server.

Dùng: python scripts/start_server.py [--host 0.0.0.0] [--port 8080] [--reload]
Port mặc định: 8080 (AgentBase contract — KHÔNG đổi cho prod).

Biến môi trường:
  LOG_FORMAT=json   → log JSON một dòng (production / log aggregator)
  LOG_FORMAT=text   → log text thường (mặc định, dev)
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# Đảm bảo src/ trong path khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import uvicorn

from dotenv import load_dotenv
load_dotenv()


def _setup_logging() -> None:
    """Cấu hình logging: JSON khi LOG_FORMAT=json, text thường khi không set."""
    log_format = os.environ.get("LOG_FORMAT", "text").lower()
    if log_format == "json":
        import json as _json

        class _JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                data = {
                    "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                    "level": record.levelname,
                    "logger": record.name,
                    "msg": record.getMessage(),
                }
                if record.exc_info:
                    data["exc"] = self.formatException(record.exc_info)
                return _json.dumps(data, ensure_ascii=False)

        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logging.root.handlers = [handler]
        logging.root.setLevel(logging.INFO)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Investigation Agent webhook server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    parser.add_argument("--reload", action="store_true", help="Hot-reload khi code thay đổi (dev only)")
    args = parser.parse_args()

    _setup_logging()

    log_fmt = os.environ.get("LOG_FORMAT", "text").lower()
    print(f"Starting Investigation Agent server on http://{args.host}:{args.port} [log={log_fmt}]")
    print("POST /trigger       — kích điều tra mới")
    print("GET  /health        — liveness probe")
    print("GET  /health/ready  — readiness probe (DB ping)")
    print("GET  /docs          — Swagger UI")
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
