PYTHON := .venv314/bin/python3
PORT   := 8080
MCP_PORT := 9000

.PHONY: help install setup db init seed server run server-reload mcp chat eval eval-fintech eval-all \
        trigger trigger-fintech test ci clean reset \
        ansible-ping ansible-postgres ansible-check

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

# ── Misc ───────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
