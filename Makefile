# ============================================================================
# ParliamentRAG — Makefile
# ============================================================================
# Usage:
#   make            — show help
#   make dev        — run locally (neo4j + backend + frontend)
#   make down       — stop everything
#   make deploy     — push to GitHub → Railway auto-deploys
# ============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR    := $(shell pwd)
BACKEND_DIR := $(ROOT_DIR)/backend
FRONTEND_DIR:= $(ROOT_DIR)/frontend
VENV        := $(BACKEND_DIR)/venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
UVICORN     := $(VENV)/bin/uvicorn

# ---------------------------------------------------------------------------
# Config (overridable)
# ---------------------------------------------------------------------------
BACKEND_PORT  ?= 8000
FRONTEND_PORT ?= 3000
WORKERS       ?= 1
BRANCH        ?= main

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
BOLD  := \033[1m
CYAN  := \033[36m
GREEN := \033[32m
RESET := \033[0m

# ============================================================================
#  Help
# ============================================================================

.PHONY: help
help: ## Show this help
	@printf "\n$(BOLD)$(CYAN)ParliamentRAG$(RESET) — Available targets:\n\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(RESET) %s\n", $$1, $$2}'
	@printf "\n"

# ============================================================================
#  Infrastructure
# ============================================================================

.PHONY: neo4j neo4j-stop neo4j-logs neo4j-status

neo4j: ## Start Neo4j (Docker)
	@docker compose up -d neo4j
	@printf "$(GREEN)Neo4j started$(RESET) — UI: http://localhost:7475\n"

neo4j-stop: ## Stop Neo4j
	@docker compose down

neo4j-logs: ## Tail Neo4j logs
	@docker compose logs -f neo4j

neo4j-status: ## Check Neo4j container status
	@docker compose ps neo4j

# ============================================================================
#  Backend
# ============================================================================

.PHONY: venv install backend backend-prod lint format test

venv: ## Create Python virtualenv
	@test -d $(VENV) || python3 -m venv $(VENV)
	@printf "$(GREEN)Virtualenv ready$(RESET) at $(VENV)\n"

install: venv ## Install backend dependencies
	@$(PIP) install --upgrade pip -q
	@$(PIP) install -r $(BACKEND_DIR)/requirements.txt -q
	@$(PYTHON) -m spacy download it_core_news_sm -q 2>/dev/null || true
	@printf "$(GREEN)Backend dependencies installed$(RESET)\n"

backend: ## Start backend (dev, auto-reload)
	@cd $(BACKEND_DIR) && $(UVICORN) app.main:app \
		--reload \
		--port $(BACKEND_PORT) \
		--log-level info

backend-prod: ## Start backend (production)
	@cd $(BACKEND_DIR) && $(UVICORN) app.main:app \
		--host 0.0.0.0 \
		--port $(BACKEND_PORT) \
		--workers $(WORKERS)

lint: ## Run linters (mypy + black --check)
	@cd $(BACKEND_DIR) && $(VENV)/bin/black --check app/
	@cd $(BACKEND_DIR) && $(VENV)/bin/isort --check-only app/
	@cd $(BACKEND_DIR) && $(VENV)/bin/mypy app/ --ignore-missing-imports

format: ## Auto-format backend code
	@cd $(BACKEND_DIR) && $(VENV)/bin/black app/
	@cd $(BACKEND_DIR) && $(VENV)/bin/isort app/
	@printf "$(GREEN)Code formatted$(RESET)\n"

test: ## Run backend tests
	@cd $(BACKEND_DIR) && $(PYTHON) -m pytest -v --tb=short

# ============================================================================
#  Frontend
# ============================================================================

.PHONY: frontend-install frontend frontend-build frontend-lint

frontend-install: ## Install frontend dependencies
	@cd $(FRONTEND_DIR) && npm install
	@printf "$(GREEN)Frontend dependencies installed$(RESET)\n"

frontend: ## Start frontend (dev)
	@cd $(FRONTEND_DIR) && npm run dev -- --port $(FRONTEND_PORT)

frontend-build: ## Build frontend for production
	@cd $(FRONTEND_DIR) && npm run build
	@printf "$(GREEN)Frontend build complete$(RESET)\n"

frontend-lint: ## Lint frontend code
	@cd $(FRONTEND_DIR) && npm run lint

# ============================================================================
#  Full Stack
# ============================================================================

.PHONY: dev down status deploy

dev: ## Run locally (Neo4j locale + backend + frontend)
	@printf "$(BOLD)Starting ParliamentRAG stack...$(RESET)\n"
	@# Stop conflicting Neo4j containers on same ports
	@for cid in $$(docker ps -q --filter "publish=7475" --filter "publish=7689"); do \
		cname=$$(docker inspect --format '{{.Name}}' $$cid | tr -d '/'); \
		if [ "$$cname" != "tesi2-neo4j" ]; then \
			printf "$(CYAN)Stopping conflicting container $$cname...$(RESET)\n"; \
			docker stop $$cid > /dev/null; \
		fi; \
	done
	@docker compose up -d neo4j
	@printf "$(CYAN)Waiting for Neo4j bolt port (7689)...$(RESET)\n"
	@for i in $$(seq 1 30); do \
		$(PYTHON) -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('$(NEO4J_LOCAL)',auth=('$(NEO4J_USER)','$(NEO4J_PASS)')); s=d.session(); s.run('RETURN 1').single(); s.close(); d.close()" 2>/dev/null && break; \
		printf "."; \
		sleep 3; \
	done
	@printf "\n$(GREEN)[1/3]$(RESET) Neo4j ready — UI: http://localhost:7475\n"
	@cd $(BACKEND_DIR) && $(UVICORN) app.main:app \
		--reload --port $(BACKEND_PORT) --log-level info &
	@sleep 2
	@printf "$(GREEN)[2/3]$(RESET) Backend started on :$(BACKEND_PORT)\n"
	@cd $(FRONTEND_DIR) && npm run dev -- --port $(FRONTEND_PORT) &
	@sleep 2
	@printf "$(GREEN)[3/3]$(RESET) Frontend started on :$(FRONTEND_PORT)\n"
	@printf "\n$(BOLD)$(GREEN)Stack is running$(RESET)\n"
	@printf "  Frontend : http://localhost:$(FRONTEND_PORT)\n"
	@printf "  Backend  : http://localhost:$(BACKEND_PORT)/docs\n"
	@printf "  Neo4j    : http://localhost:7475\n\n"

down: ## Stop everything (Neo4j + backend + frontend)
	@printf "Stopping services...\n"
	@-pkill -f "uvicorn app.main:app" 2>/dev/null || true
	@-pkill -f "next dev" 2>/dev/null || true
	@docker compose down
	@printf "$(GREEN)All services stopped$(RESET)\n"

status: ## Show status of all services
	@printf "\n$(BOLD)Service Status$(RESET)\n"
	@printf "%-12s " "Neo4j:"; \
		docker compose ps --format '{{.State}}' neo4j 2>/dev/null || printf "stopped"
	@printf "\n"
	@printf "%-12s " "Backend:"; \
		(pgrep -f "uvicorn app.main:app" > /dev/null && printf "running (pid %s)" "$$(pgrep -f 'uvicorn app.main:app' | head -1)") || printf "stopped"
	@printf "\n"
	@printf "%-12s " "Frontend:"; \
		(pgrep -f "next dev" > /dev/null && printf "running (pid %s)" "$$(pgrep -f 'next dev' | head -1)") || printf "stopped"
	@printf "\n\n"

# ============================================================================
#  Deploy (GitHub → Railway)
# ============================================================================

deploy: ## Deploy to production (git push → Railway)
	@printf "$(BOLD)Deploying to production...$(RESET)\n"
	@# Ensure working tree is clean
	@if [ -n "$$(git status --porcelain)" ]; then \
		printf "$(CYAN)Uncommitted changes found:$(RESET)\n"; \
		git status --short; \
		printf "\n"; \
		read -p "Commit all changes before deploying? [y/N] " yn; \
		if [ "$$yn" = "y" ] || [ "$$yn" = "Y" ]; then \
			read -p "Commit message: " msg; \
			git add -A && git commit -m "$$msg"; \
		else \
			printf "Aborting deploy.\n"; exit 1; \
		fi; \
	fi
	@# Push to GitHub (Railway picks up automatically)
	@printf "$(CYAN)Pushing $(BRANCH) to origin...$(RESET)\n"
	@git push origin $(BRANCH)
	@printf "\n$(BOLD)$(GREEN)Deployed!$(RESET) Railway will pick up the push automatically.\n"
	@printf "  GitHub : https://github.com/Emeierkeio/thesis-ParliamentRAG\n\n"

# ============================================================================
#  Setup & Utilities
# ============================================================================

.PHONY: setup env-check clean docker-build

setup: env-check install frontend-install ## First-time setup (install all deps)
	@printf "\n$(BOLD)$(GREEN)Setup complete!$(RESET) Run $(CYAN)make up$(RESET) to start.\n"

env-check: ## Verify .env file exists
	@test -f .env || (cp .env.example .env && \
		printf "$(CYAN)Created .env from .env.example — edit it with your keys$(RESET)\n")
	@$(PYTHON) -c "\
		missing=[]; \
		import os; \
		[missing.append(k) for k in ['NEO4J_URI','NEO4J_PASSWORD','OPENAI_API_KEY'] \
			if not os.environ.get(k) and k+'=' not in open('.env').read()]; \
		exit(0)" 2>/dev/null || true

clean: ## Remove build artifacts and caches
	@rm -rf $(FRONTEND_DIR)/.next
	@rm -rf $(BACKEND_DIR)/__pycache__ $(BACKEND_DIR)/app/__pycache__
	@find $(BACKEND_DIR) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find $(BACKEND_DIR) -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@printf "$(GREEN)Cleaned$(RESET)\n"

docker-build: ## Build backend Docker image
	@docker build -t parliament-rag-backend $(BACKEND_DIR)
	@printf "$(GREEN)Docker image built$(RESET)\n"

# ============================================================================
#  Database Pipeline
# ============================================================================

BUILD_DIR    := $(ROOT_DIR)/build
BUILD_SCRIPT := $(BUILD_DIR)/build_and_update.py
NEO4J_LOCAL  := bolt://localhost:7689
NEO4J_USER   ?= neo4j
NEO4J_PASS   ?= thesis2026

.PHONY: db-populate db-update db-senate db-download-csv db-install

db-install: venv ## Install build dependencies (pandas, regex, etc.)
	@$(PIP) install -r $(BUILD_DIR)/requirements-build.txt -q
	@printf "$(GREEN)Build dependencies installed$(RESET)\n"

db-download-csv: db-install ## Download deputy CSVs from dati.camera.it
	@$(PYTHON) $(BUILD_DIR)/download_deputies_csv.py

db-all: db-install ## One-shot full DB: download CSVs + build + chunk + embed + vector index
	@printf "$(BOLD)$(CYAN)Full database build (one-shot)...$(RESET)\n"
	@# 1. Stop backend/frontend if running
	@-pkill -f "uvicorn app.main:app" 2>/dev/null || true
	@-pkill -f "next dev" 2>/dev/null || true
	@# 2. Start Neo4j (or ensure it's running)
	@docker compose up -d neo4j
	@printf "$(CYAN)Waiting for Neo4j bolt port (7689)...$(RESET)\n"
	@for i in $$(seq 1 30); do \
		$(PYTHON) -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('$(NEO4J_LOCAL)',auth=('$(NEO4J_USER)','$(NEO4J_PASS)')); s=d.session(); s.run('RETURN 1').single(); s.close(); d.close()" 2>/dev/null && break; \
		printf "."; \
		sleep 3; \
	done
	@printf "\n$(GREEN)Neo4j ready$(RESET)\n"
	@# 3. Always re-download CSVs for freshest data
	@printf "$(CYAN)Downloading deputy CSVs from dati.camera.it...$(RESET)\n"
	@$(PYTHON) $(BUILD_DIR)/download_deputies_csv.py
	@# 4. Full build: nuke → ingest → chunk → vector index → embeddings
	@$(PYTHON) $(BUILD_SCRIPT) build \
		--neo4j-uri $(NEO4J_LOCAL) \
		--neo4j-user $(NEO4J_USER) \
		--neo4j-password $(NEO4J_PASS)
	@printf "$(CYAN)Building Senate data (additive)...$(RESET)\n"
	@$(PYTHON) $(BUILD_SCRIPT) build-senate \
		--neo4j-uri $(NEO4J_LOCAL) \
		--neo4j-user $(NEO4J_USER) \
		--neo4j-password $(NEO4J_PASS)
	@printf "\n$(BOLD)$(GREEN)Database ready!$(RESET) Run $(CYAN)make dev$(RESET) to start the stack.\n"
	@printf "  Then run $(CYAN)make compute-baseline$(RESET) with the backend up to pre-calc baseline experts.\n"

db-populate: db-install ## Full DB build (skip CSV download if present)
	@printf "$(BOLD)$(CYAN)Full database populate...$(RESET)\n"
	@# 1. Stop backend/frontend if running
	@-pkill -f "uvicorn app.main:app" 2>/dev/null || true
	@-pkill -f "next dev" 2>/dev/null || true
	@# 2. Start Neo4j (or ensure it's running)
	@docker compose up -d neo4j
	@printf "$(CYAN)Waiting for Neo4j bolt port (7689)...$(RESET)\n"
	@for i in $$(seq 1 30); do \
		$(PYTHON) -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('$(NEO4J_LOCAL)',auth=('$(NEO4J_USER)','$(NEO4J_PASS)')); s=d.session(); s.run('RETURN 1').single(); s.close(); d.close()" 2>/dev/null && break; \
		printf "."; \
		sleep 3; \
	done
	@printf "\n$(GREEN)Neo4j ready$(RESET)\n"
	@# 3. Download CSVs if missing
	@test -f $(ROOT_DIR)/data/deputati_xix.csv || \
		(printf "$(CYAN)CSV files not found — downloading from dati.camera.it...$(RESET)\n" && \
		 $(PYTHON) $(BUILD_DIR)/download_deputies_csv.py)
	@# 4. Run build
	@$(PYTHON) $(BUILD_SCRIPT) build \
		--neo4j-uri $(NEO4J_LOCAL) \
		--neo4j-user $(NEO4J_USER) \
		--neo4j-password $(NEO4J_PASS)
	@printf "\n$(BOLD)$(GREEN)Database populated!$(RESET) Run $(CYAN)make dev$(RESET) to start the stack.\n"

db-update: db-install ## Incremental update (start Neo4j if needed, download new XMLs + acts)
	@printf "$(BOLD)$(CYAN)Updating Neo4j database...$(RESET)\n"
	@# 1. Stop backend/frontend if running
	@-pkill -f "uvicorn app.main:app" 2>/dev/null || true
	@-pkill -f "next dev" 2>/dev/null || true
	@# 2. Start Neo4j (or ensure it's running)
	@docker compose up -d neo4j
	@printf "$(CYAN)Waiting for Neo4j bolt port (7689)...$(RESET)\n"
	@for i in $$(seq 1 30); do \
		$(PYTHON) -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('$(NEO4J_LOCAL)',auth=('$(NEO4J_USER)','$(NEO4J_PASS)')); s=d.session(); s.run('RETURN 1').single(); s.close(); d.close()" 2>/dev/null && break; \
		printf "."; \
		sleep 3; \
	done
	@printf "\n$(GREEN)Neo4j ready$(RESET)\n"
	@# 3. Run update
	@$(PYTHON) $(BUILD_SCRIPT) update \
		--neo4j-uri $(NEO4J_LOCAL) \
		--neo4j-user $(NEO4J_USER) \
		--neo4j-password $(NEO4J_PASS)
	@printf "\n$(BOLD)$(GREEN)Database updated!$(RESET) Run $(CYAN)make dev$(RESET) to start the stack.\n"

db-senate: db-install ## Build Senate data (additive, Camera data preserved)
	@printf "$(BOLD)$(CYAN)Senate database build (additive)...$(RESET)\n"
	@docker compose up -d neo4j
	@printf "$(CYAN)Waiting for Neo4j bolt port (7689)...$(RESET)\n"
	@for i in $$(seq 1 30); do \
		$(PYTHON) -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('$(NEO4J_LOCAL)',auth=('$(NEO4J_USER)','$(NEO4J_PASS)')); s=d.session(); s.run('RETURN 1').single(); s.close(); d.close()" 2>/dev/null && break; \
		printf "."; \
		sleep 3; \
	done
	@printf "\n$(GREEN)Neo4j ready$(RESET)\n"
	@$(PYTHON) $(BUILD_SCRIPT) build-senate \
		--neo4j-uri $(NEO4J_LOCAL) \
		--neo4j-user $(NEO4J_USER) \
		--neo4j-password $(NEO4J_PASS)
	@printf "\n$(BOLD)$(GREEN)Senate data built!$(RESET)\n"

# ============================================================================
#  Graph Enrichment (SPARQL)
# ============================================================================

.PHONY: enrich-sparql enrich-sparql-test

enrich-sparql: db-install ## Enrich graph from dati.camera.it SPARQL (votes + committee roles)
	@printf "$(BOLD)$(CYAN)SPARQL enrichment from dati.camera.it...$(RESET)\n"
	@docker compose up -d neo4j
	@printf "$(CYAN)Waiting for Neo4j bolt port (7689)...$(RESET)\n"
	@for i in $$(seq 1 30); do \
		$(PYTHON) -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('$(NEO4J_LOCAL)',auth=('$(NEO4J_USER)','$(NEO4J_PASS)')); s=d.session(); s.run('RETURN 1').single(); s.close(); d.close()" 2>/dev/null && break; \
		printf "."; \
		sleep 3; \
	done
	@printf "\n$(GREEN)Neo4j ready$(RESET)\n"
	@$(PYTHON) $(BUILD_DIR)/sparql_ingester.py \
		--neo4j-uri $(NEO4J_LOCAL) \
		--neo4j-user $(NEO4J_USER) \
		--neo4j-password $(NEO4J_PASS)
	@printf "\n$(BOLD)$(GREEN)SPARQL enrichment complete!$(RESET)\n"

enrich-sparql-test: db-install ## Test SPARQL enrichment with 5 deputies only
	@$(PYTHON) $(BUILD_DIR)/sparql_ingester.py \
		--neo4j-uri $(NEO4J_LOCAL) \
		--neo4j-user $(NEO4J_USER) \
		--neo4j-password $(NEO4J_PASS) \
		--limit-deputies 5

# ============================================================================
#  Backend Scripts
# ============================================================================

.PHONY: seed-eval compute-baseline compute-spread

seed-eval: ## Seed evaluation topics into Neo4j
	@cd $(BACKEND_DIR) && $(PYTHON) scripts/seed_evaluation_topic.py

compute-baseline: ## Compute baseline experts for evaluation set
	@cd $(BACKEND_DIR) && $(PYTHON) scripts/compute_baseline_experts.py

compute-spread: ## Compute topic authority spread
	@cd $(BACKEND_DIR) && $(PYTHON) scripts/compute_topic_authority_spread.py
