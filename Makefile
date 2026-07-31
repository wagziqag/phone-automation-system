# phone-automation-system Makefile
# Usage: make [target]

SHELL := /bin/bash
PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
CONFIG_DIR := $(HOME)/.phone-assistant

.PHONY: help install check update clean test deploy sync status

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Full install (deps + config + verify)
	@echo "=== phone-automation-system install ==="
	@echo "[1/4] Checking Python..."
	@python3 --version || { echo "ERROR: python3 required"; exit 1; }
	@echo "[2/4] Creating config directory..."
	@mkdir -p $(CONFIG_DIR)
	@echo "[3/4] Installing Python dependencies..."
	@pip install -q requests ollama 2>/dev/null || echo "  pip install skipped (already installed?)"
	@echo "[4/4] Verifying..."
	@python3 -c "from marvis_orchestrator import MarvisHub; h=MarvisHub(); print(f'  MarvisHub OK (ver={h.VERSION})')" || echo "  marvis_orchestrator not available"
	@echo "Install complete. Run 'make check' to verify."

check: ## Health check (Shizuku/ADB/Ollama/Termux:API)
	@echo "=== Health Check ==="
	@echo -n "Shizuku: "; adb shell sh /sdcard/Android/data/moe.shizuku.privileged.api/start.sh 2>/dev/null && echo "OK" || echo "SKIP"
	@echo -n "ADB:     "; adb devices 2>/dev/null | grep -q 'device$$' && echo "OK" || echo "FAIL"
	@echo -n "Ollama:  "; curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && echo "OK" || echo "FAIL (start with: ollama serve &)"
	@echo -n "Models:  "; ollama list 2>/dev/null | tail -n +2 | wc -l | xargs echo
	@echo -n "Git:     "; git log --oneline -1 2>/dev/null || echo "N/A"
	@echo -n "Config:  "; test -f $(CONFIG_DIR)/app_cache.json && echo "OK" || echo "MISSING"
	@echo -n "Disk:    "; df -h $(PROJECT_DIR) 2>/dev/null | tail -1 | awk '{print $$5" used ("$$4" free)"}'

update: ## Git pull + reload config
	@echo "=== Update ==="
	@git fetch origin
	@git reset --hard origin/master
	@echo "Updated to: $$(git log --oneline -1)"
	@python3 scripts/app_cache_refresher.py 2>/dev/null || echo "  cache refresh skipped"
	@echo "Update complete."

clean: ## Clean temp files
	@echo "=== Clean ==="
	@find $(PROJECT_DIR) -name "*.pyc" -delete 2>/dev/null || true
	@find $(PROJECT_DIR) -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@test -d $(CONFIG_DIR)/logs && find $(CONFIG_DIR)/logs -name "*.log" -mtime +7 -delete 2>/dev/null || true
	@echo "Cleaned pyc/pycache/old logs."

test: ## Run regression tests
	@echo "=== Test Suite ==="
	@echo "[1] Core imports (marvis_orchestrator / v4_server)..."
	@python3 -c "from marvis_orchestrator import MarvisHub; from v4_server import HAS_FLASK; print('  OK')" || echo "  FAIL"
	@echo "[2] Learning core (evolution_v2.ExperienceReplay)..."
	@python3 -c "from evolution_v2 import ExperienceReplay; er=ExperienceReplay(); er.load(); print('  OK')" || echo "  FAIL"
	@echo "[3] Loop + performance monitor..."
	@python3 -c "from modules.autonomous_loop import run_task; from modules.performance_monitor import PerformanceMonitor; print('  OK')" || echo "  FAIL"
	@echo "[4] Model finetuner CLI..."
	@python3 -c "from modules.model_finetuner import _main; print('  OK')" || echo "  FAIL"
	@echo "Test complete."

deploy: install check ## Full deploy (install + check)
	@echo "Deploy complete."

sync: ## Sync from Gitee (full)
	@echo "=== Sync ==="
	@git fetch origin
	@git reset --hard origin/master
	@git clean -fd
	@echo "Synced to: $$(git log --oneline -1)"

status: ## Show system status
	@echo "=== System Status ==="
	@echo "Project: $(PROJECT_DIR)"
	@echo -n "Git HEAD: "; git log --oneline -1 2>/dev/null || echo "N/A"
	@echo -n "Ollama models: "; ollama list 2>/dev/null | tail -n +2 | wc -l | xargs echo || echo "N/A"
	@echo -n "App cache: "; test -f $(CONFIG_DIR)/app_cache.json && python3 -c "import json; d=json.load(open('$(CONFIG_DIR)/app_cache.json')); print(f'{len(d)} apps')" || echo "MISSING"
	@echo -n "Disk: "; df -h $(PROJECT_DIR) 2>/dev/null | tail -1 | awk '{print $$5" used ("$$4" free)"}'
	@echo -n "Python: "; python3 --version 2>&1
