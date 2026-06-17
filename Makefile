PYTHON := .venv314/bin/python3
PORT   := 8080
MCP_PORT := 9000
GITLAB_MCP_PORT := 9002

# Nạp .env vào recipe (DB_BACKEND, DATABASE_URL, GITLAB_*, DEMO_CHAT_ID...)
LOADENV := set -a; [ -f .env ] && . ./.env; set +a;

.PHONY: help install setup db init seed server run server-reload mcp chat eval eval-fintech eval-all \
        trigger trigger-fintech test ci clean reset \
        ansible-ping ansible-postgres ansible-check \
        demo-prep demo-seed demo-gitlab demo-setup demo-up demo-down demo-webhook

# ── Default ────────────────────────────────────────────────────────────────────
help:
	@echo "Investigation Agent — lệnh thường dùng"
	@echo ""
	@echo "  make install        Tạo venv + cài dependencies"
	@echo "  make setup          install + db + seed (khởi động từ đầu)"
	@echo ""
	@echo "  make run            Khởi động server port $(PORT)  (alias: server)"
	@echo "  make server-reload  Khởi động server với --reload (dev)"
	@echo "  make mcp            Khởi động MCP server port $(MCP_PORT)"
	@echo ""
	@echo "  make init           Init DB + chạy tất cả migration  (alias: db)"
	@echo "  make seed           Seed tất cả 6 kịch bản"
	@echo "  make reset          Xóa DB + init lại + seed lại"
	@echo ""
	@echo "  make eval           Eval 4 microservice scenario N=3 (mock)"
	@echo "  make eval-fintech   Eval 2 fintech scenario N=3 (mock)"
	@echo "  make eval-all       Eval tất cả 6 scenario N=10 (mock)"
	@echo ""
	@echo "  make chat           CLI REPL chat với agent"
	@echo "  make trigger sc=1   Trigger scenario (sc=1|2|3|4|f1|f2)"
	@echo ""
	@echo "  make test           Chạy pytest (173 tests)"
	@echo "  make ci             pytest + eval gate (cổng CI)"
	@echo ""
	@echo "  make clean          Xóa __pycache__ và file tạm"
	@echo ""
	@echo "  ── DEMO (docs/DEMO.md) ──"
	@echo "  make demo-prep      Seed demo + push GitLab source + provision project (1 lần)"
	@echo "  make demo-up        Chạy CÙNG LÚC 3 server: telemetry:$(MCP_PORT) · gitlab-code:$(GITLAB_MCP_PORT) · main:$(PORT)"
	@echo "  make demo-webhook [src=prometheus|grafana|sentry|opsgenie|simple]  Bắn 1 webhook"
	@echo "  make demo-down      Dừng cả 3 server demo"

# ── Setup ──────────────────────────────────────────────────────────────────────
install:
	python3.14 -m venv .venv314
	.venv314/bin/pip install -e ".[dev]"

setup: install db seed
	@echo "✅ Sẵn sàng — chạy: make server"

# ── Database ───────────────────────────────────────────────────────────────────
init: db

db:
	$(PYTHON) data/init_db.py
	$(PYTHON) data/migrate_projects.py
	$(PYTHON) data/migrate_fintech.py

seed:
	$(PYTHON) data/seed_scenario1.py
	$(PYTHON) data/seed_scenario2.py
	$(PYTHON) data/seed_scenario3.py
	$(PYTHON) data/seed_scenario4.py
	$(PYTHON) data/seed_fintech1.py
	$(PYTHON) data/seed_fintech2.py

reset:
	rm -f data/investigation.db
	$(MAKE) db seed
	@echo "✅ DB đã reset và seed lại"

# ── Servers ────────────────────────────────────────────────────────────────────
run: server

server:
	$(PYTHON) scripts/start_server.py --port $(PORT)

server-reload:
	$(PYTHON) scripts/start_server.py --port $(PORT) --reload

mcp:
	$(PYTHON) scripts/start_mcp_server.py --port $(MCP_PORT)

# ── CLI ────────────────────────────────────────────────────────────────────────
chat:
	$(PYTHON) scripts/chat.py

# make trigger sc=1  →  scenario1 | sc=f1 → fintech1
trigger:
	@sc=$(sc); \
	case "$$sc" in \
	  1)  $(PYTHON) scripts/trigger.py --scenario scenario1 ;; \
	  2)  $(PYTHON) scripts/trigger.py --scenario scenario2 ;; \
	  3)  $(PYTHON) scripts/trigger.py --scenario scenario3 ;; \
	  4)  $(PYTHON) scripts/trigger.py --scenario scenario4 ;; \
	  f1) $(PYTHON) scripts/trigger.py --scenario fintech1 ;; \
	  f2) $(PYTHON) scripts/trigger.py --scenario fintech2 ;; \
	  *)  echo "Dùng: make trigger sc=1|2|3|4|f1|f2" ;; \
	esac

# ── Eval ───────────────────────────────────────────────────────────────────────
eval:
	$(PYTHON) scripts/eval_agent.py --mock --n 3

eval-fintech:
	$(PYTHON) scripts/eval_fintech.py --n 3

eval-all:
	$(PYTHON) scripts/eval_agent.py --mock --n 10
	$(PYTHON) scripts/eval_fintech.py --n 10

# ── Test / CI ──────────────────────────────────────────────────────────────────
test:
	$(PYTHON) -m pytest --tb=short -q

ci: test
	$(PYTHON) scripts/eval_agent.py --mock --n 3 --scenario all
	@echo "✅ CI gate PASS"

# ── Ansible / Deploy ───────────────────────────────────────────────────────────
ansible-ping:
	cd deployment && ansible all -m ping

ansible-check:
	cd deployment && ansible-playbook playbooks/deploy_postgres.yml --check

ansible-postgres:
	cd deployment && ansible-playbook playbooks/deploy_postgres.yml

# ── Demo (xem docs/DEMO.md) ────────────────────────────────────────────────────
# Prep 1 lần: seed data + push source GitLab + provision project.
demo-prep: demo-seed demo-gitlab demo-setup
	@echo "✅ Demo sẵn sàng — chạy: make demo-up  (rồi: make demo-webhook)"

demo-seed:
	@$(LOADENV) $(PYTHON) data/seed_demo.py

demo-gitlab:
	@$(LOADENV) bash demo/setup_gitlab_repos.sh

demo-setup:
	@$(LOADENV) $(PYTHON) scripts/setup_demo.py

# Chạy cùng lúc 3 server, Ctrl-C dừng tất cả (trap kill toàn process group).
demo-up:
	@echo "🚀 telemetry:$(MCP_PORT) · gitlab-code:$(GITLAB_MCP_PORT) · main:$(PORT) — Ctrl-C để dừng tất cả"
	@$(LOADENV) trap 'kill 0' INT TERM EXIT; \
	  $(PYTHON) scripts/start_mcp_server.py --port $(MCP_PORT) & \
	  $(PYTHON) scripts/start_gitlab_code_mcp.py --port $(GITLAB_MCP_PORT) & \
	  $(PYTHON) scripts/start_server.py --port $(PORT) & \
	  wait

demo-down:
	@for p in $(PORT) $(MCP_PORT) $(GITLAB_MCP_PORT); do lsof -ti tcp:$$p | xargs -r kill -9 2>/dev/null || true; done
	@echo "🛑 Đã dừng 3 server demo"

# make demo-webhook            → prometheus
# make demo-webhook src=sentry → sentry
demo-webhook:
	@$(LOADENV) bash demo/webhooks/$(or $(src),prometheus).sh

# ── Misc ───────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
