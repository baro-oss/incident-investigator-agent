# ── Build stage ───────────────────────────────────────────────────────────────
# linux/amd64 bắt buộc cho GreenNode AgentBase (CR vcr.vngcloud.vn)
FROM --platform=linux/amd64 python:3.14-slim AS builder

WORKDIR /build

COPY pyproject.toml ./
COPY src/ src/

# Cài deps vào prefix riêng — không ảnh hưởng image base
RUN pip install --no-cache-dir --prefix=/install -e ".[postgres]"

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM --platform=linux/amd64 python:3.14-slim

# Non-root user (AgentBase best-practice + security)
RUN addgroup --system agent && adduser --system --ingroup agent agent

WORKDIR /app

# Copy installed packages từ builder
COPY --from=builder /install /usr/local

# Copy app source (không cần dev files)
COPY --chown=agent:agent src/ src/
COPY --chown=agent:agent scripts/ scripts/
COPY --chown=agent:agent data/schema.sql data/schema.sql
COPY --chown=agent:agent data/schema_postgres.sql data/schema_postgres.sql
COPY --chown=agent:agent data/init_db.py data/init_db.py
COPY --chown=agent:agent data/migrate_fintech.py data/migrate_fintech.py
COPY --chown=agent:agent mcp_server/ mcp_server/
COPY --chown=agent:agent pyproject.toml ./

# Tạo data dir cho SQLite dev (PG prod không dùng nhưng init_db.py cần thư mục)
RUN mkdir -p /app/data && chown agent:agent /app/data

USER agent

# Port 8080 — AgentBase hard contract (KHÔNG đổi)
EXPOSE 8080

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=8080

# HEALTHCHECK → AgentBase và docker-compose biết container đã sẵn sàng
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" \
    || exit 1

# Entrypoint: init DB (idempotent) rồi start server
CMD ["sh", "-c", "python data/init_db.py && python scripts/start_server.py --host 0.0.0.0 --port 8080"]
