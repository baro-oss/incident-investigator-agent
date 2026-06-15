# Investigation Agent

Agent điều tra sự cố tự động cho hệ microservice và fintech. Nhận triệu chứng (webhook alert hoặc trigger thủ công) → engine điều tra domain-agnostic qua adaptive loop + tool-calling → verdict neo bằng chứng → push Telegram/Teams/Email.

## Kiến trúc 4 cạnh pluggable

```
             ┌──────────────────── ENGINE ─────────────────────┐
             │                                                   │
INTAKE       │  decide_next_action(state, llm, tools)           │  OUTPUT
──────────   │  ──────────────────────────────────────────────  │  ────────
Prometheus   │  • LLM chọn tool tiếp theo (adaptive)            │  Telegram
Grafana      │  • run_tool → Observation (aggregate, ≤5 rows)  │  Teams
Sentry       │  • update_state (hypothesis lifecycle)           │  Email
PagerDuty    │  • stop khi: verdict / budget / loop detect      │  Callback
OpsGenie     │                          │                        │
GitHub       │              ┌───────────▼──────────┐            │
GitLab       │              │    Tool Registry     │            │  MODEL
             │              │  (local + MCP hot-   │            │  ────────
             │              │   plug, per-project) │            │  Anthropic
             │              └──────────────────────┘            │  OpenAI
             │                   TOOL cạnh                       │  Groq/Mistral
             └───────────────────────────────────────────────────┘
```

Engine **bất biến** ở giữa. Mỗi cạnh thêm adapter — không sửa engine.

## Quickstart

```bash
# 1. Clone + venv
git clone <repo> && cd Clawathon
python3 -m venv .venv && source .venv/bin/activate

# 2. Env vars
cp .env.example .env        # điền ANTHROPIC_API_KEY (tùy chọn — mock LLM chạy không cần)

# 3. Setup (DB + seed data)
make init                   # init DB + migrations
make seed                   # seed 6 kịch bản (4 microservice + 2 fintech)

# 4. Chạy server
make run                    # API server :8000

# 5. Trigger điều tra
make trigger sc=1           # kịch bản 1 (deploy bug)
# Hoặc HTTP:
curl -X POST localhost:8000/trigger \
  -H "Content-Type: application/json" \
  -d '{"service":"payment-gateway","scenario":"scenario1","time_window":"14:00-15:00"}'
```

Mở **dashboard:** http://localhost:8000/dashboard

## Lệnh `make`

| Target | Mô tả |
|--------|-------|
| `make setup` | Cài đặt đầy đủ từ đầu (install + init + seed) |
| `make init` | Init DB + chạy migrations |
| `make seed` | Seed 6 kịch bản |
| `make run` | Khởi động server port 8000 |
| `make mcp` | Khởi động MCP demo server port 9000 |
| `make test` | pytest (173 tests) |
| `make eval` | Eval gate mock 4 kịch bản (CI gate) |
| `make ci` | test + eval (cổng CI đầy đủ) |
| `make trigger sc=1` | Trigger kịch bản (sc=1\|2\|3\|4\|f1\|f2) |
| `make chat` | CLI REPL chat với agent |
| `make reset` | Xóa DB + khởi tạo lại |

## Kịch bản demo (7 phút)

| # | Kịch bản | Engine path |
|---|----------|-------------|
| 1 | Deploy bug: payment-gateway v2.3.1 → lỗi 502 | 5 bước, verdict HIGH |
| 2 | DB pool exhaustion: auth-service → timeout | 8 bước, verdict HIGH |
| 3 | Provider sập: MoMo gateway → lỗi thanh toán | 6 bước, verdict HIGH |
| 4 | Traffic surge 5x → rate limit api-gateway | 3 bước, verdict HIGH |
| f1 | Fintech: processor timeout → thanh toán thất bại | multi-agent |
| f2 | Fintech: price bug merchant → doanh thu lệch | multi-agent |

**Luồng đầy đủ:**
```
make trigger sc=1
→ POST /projects/default/trigger
→ engine điều tra (adaptive loop, 5 bước)
→ submit_verdict tool call → Verdict(confidence=high)
→ push Telegram + lưu trace
→ http://localhost:8000/dashboard (xem kết quả realtime qua SSE)
```

## Cấu trúc chính

```
src/agent/
├── engine/       loop.py (engine) · state.py · graph.py (LangGraph) · multi_agent.py
├── tools/        contracts.py (seam) · registry.py · các tool local
├── intake/       server.py (API) · adapters/ · runner.py · scheduler.py
├── output/       telegram.py · teams.py · email.py · slack.py · callback.py
├── llm/          factory.py · anthropic.py · openai_compat.py
├── dashboard/    router.py · templates/
└── storage/      db.py (SQLite WAL)
```

## Tài liệu

| File | Nội dung |
|------|----------|
| `docs/02-architecture.md` | Kiến trúc chi tiết, 4 nguyên tắc, đường ranh |
| `docs/04-hop-dong-tool-va-observation.md` | Hợp đồng tool + Observation schema |
| `docs/05-engine.md` | Engine loop, hypothesis lifecycle, verdict |
| `docs/api.md` | API reference đầy đủ (REST + Dashboard) |
| `CLAUDE.md` | Chỉ thị vận hành dự án (chỉ thị bắt buộc cho Claude Code) |
| `BUILD_STATE.md` | Trạng thái build hiện tại |

## Bốn nguyên tắc kiến trúc

1. **LLM không thấy dữ liệu thô** — tool aggregate bằng SQL, trả Observation đã chưng cất.
2. **Một đường ranh** — engine chỉ thấy `list[Tool]` đồng nhất; không biết "log"/"SQLite"/"MCP" là gì.
3. **Lõi deterministic, agent chỉ điều phối** — tính toán trong tool; LLM chọn tool + quyết điểm dừng.
4. **Async từ biên nhận; một nguồn structured, nhiều renderer** — Observation/verdict structured, render text chỉ ở biên tiêu thụ.

## Stack

Python 3.14 · FastAPI · SQLite WAL · Anthropic API (OpenAI-compat: Groq, Mistral) · asyncio background task · MCP JSON-RPC 2.0 over HTTP
