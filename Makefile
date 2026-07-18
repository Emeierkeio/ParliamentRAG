# ParliamentRAG-demo — local development
#
# Usage:
#   make dev                          # backend (:8000) + frontend (:3000)
#   make dev BACKEND_PORT=8001 FRONTEND_PORT=3001
#   make dev-backend                  # backend only
#   make dev-frontend                 # frontend only
#   make stop                         # kill whatever is listening on the two ports
#   make install                      # install backend + frontend dependencies
#   make build                        # production build of the frontend
#   make update-data                  # ingest new Camera sessions into the demo DB (via v2 pipeline)
#   make update-data DEMO_NEO4J=bolt://localhost:7691   # same, but against the LOCAL copy (staging)
#   make db-backup                    # dated dump of the remote DB on the server (few min downtime)
#   make db-pull                      # download latest dump + restore into a local Neo4j (:7691)
#   make db-use-local / db-use-remote # switch NEO4J_URI in .env between local copy and remote

BACKEND_PORT  ?= 8000
FRONTEND_PORT ?= 3000

BACKEND_DIR  := backend
FRONTEND_DIR := frontend
UVICORN      := $(BACKEND_DIR)/venv/bin/uvicorn

# Data-update settings: the demo DB is REMOTE (server 89.167.54.206), reached
# through an SSH tunnel on local port 7690. The ingestion pipeline lives in the
# v2 repo (../ParliamentRAG/build) and is schema-compatible with this DB.
V2_DIR       ?= ../ParliamentRAG
DEMO_NEO4J   ?= bolt://localhost:7690
SSH_HOST     := root@89.167.54.206
TUNNEL_CMD   := ssh -f -N -L 7690:localhost:7687 $(SSH_HOST)

# Remote Neo4j (deployed demo) and local staging copy
REMOTE_NEO4J_CONTAINER := parliament-neo4j
REMOTE_NEO4J_VOLUME    := parliament-rag_neo4j_data
REMOTE_BACKUP_DIR      := /root/neo4j-backups
LOCAL_NEO4J_NAME       := demo-neo4j-local
LOCAL_NEO4J_VOLUME     := demo_neo4j_local_data
LOCAL_BOLT_PORT        := 7691
LOCAL_HTTP_PORT        := 7477
LOCAL_BACKUP_DIR       := $(CURDIR)/neo4j-local-backups

.PHONY: help dev dev-backend dev-frontend stop install install-backend install-frontend build check-ports update-data tunnel db-backup db-pull db-use-local db-use-remote

help:
	@grep -E '^#   make' Makefile | sed 's/^#   //'

## Run backend + frontend together; Ctrl+C stops both.
## If the default ports are taken (e.g. by the v2 project), the next free ones are picked automatically.
## Next.js allows a single `next dev` per project dir (.next/dev/lock): any duplicate
## instance of THIS project is stopped first, and stale locks are cleaned.
## The SSH tunnel to the remote Neo4j (:7690) is checked and (re)opened automatically —
## it silently dies on network changes (e.g. switching WiFi).
dev: tunnel
	@DUP=$$(pgrep -f "$(CURDIR)/frontend/node_modules/.bin/next dev" 2>/dev/null || true); \
	if [ -n "$$DUP" ]; then \
		echo "NOTE: another next dev of this project is running (PID $$DUP) — stopping it to avoid the .next/dev/lock conflict."; \
		kill $$DUP 2>/dev/null || true; sleep 2; \
	fi; \
	rm -f $(FRONTEND_DIR)/.next/dev/lock
	@BP=$(BACKEND_PORT); FP=$(FRONTEND_PORT); \
	while lsof -ti tcp:$$BP >/dev/null 2>&1; do BP=$$((BP+1)); done; \
	while lsof -ti tcp:$$FP >/dev/null 2>&1; do FP=$$((FP+1)); done; \
	if [ "$$BP" != "$(BACKEND_PORT)" ] || [ "$$FP" != "$(FRONTEND_PORT)" ]; then \
		echo "NOTE: requested ports busy — using backend :$$BP, frontend :$$FP"; \
	fi; \
	echo "→ backend  http://localhost:$$BP"; \
	echo "→ frontend http://localhost:$$FP"; \
	trap 'kill 0' INT TERM EXIT; \
	( cd $(BACKEND_DIR) && venv/bin/uvicorn app.main:app --reload --port $$BP ) & \
	( cd $(FRONTEND_DIR) && BACKEND_URL=http://localhost:$$BP npx next dev --port $$FP ) & \
	wait

dev-backend:
	@cd $(BACKEND_DIR) && venv/bin/uvicorn app.main:app --reload --port $(BACKEND_PORT)

dev-frontend:
	@cd $(FRONTEND_DIR) && BACKEND_URL=http://localhost:$(BACKEND_PORT) npx next dev --port $(FRONTEND_PORT)

## Fail fast with a clear message if a port is taken (e.g. the v2 project on :8000/:3000).
check-ports:
	@if lsof -ti tcp:$(BACKEND_PORT) >/dev/null 2>&1; then \
		echo "ERROR: port $(BACKEND_PORT) already in use (PID $$(lsof -ti tcp:$(BACKEND_PORT) | head -1))."; \
		echo "  Either: make stop BACKEND_PORT=$(BACKEND_PORT)"; \
		echo "  Or:     make dev BACKEND_PORT=8001 FRONTEND_PORT=3001"; \
		exit 1; \
	fi
	@if lsof -ti tcp:$(FRONTEND_PORT) >/dev/null 2>&1; then \
		echo "ERROR: port $(FRONTEND_PORT) already in use (PID $$(lsof -ti tcp:$(FRONTEND_PORT) | head -1))."; \
		echo "  Either: make stop FRONTEND_PORT=$(FRONTEND_PORT)"; \
		echo "  Or:     make dev BACKEND_PORT=8001 FRONTEND_PORT=3001"; \
		exit 1; \
	fi

## Kill whatever is listening on BACKEND_PORT / FRONTEND_PORT.
stop:
	-@lsof -ti tcp:$(BACKEND_PORT)  | xargs kill 2>/dev/null || true
	-@lsof -ti tcp:$(FRONTEND_PORT) | xargs kill 2>/dev/null || true
	@echo "Freed ports $(BACKEND_PORT) and $(FRONTEND_PORT)."

## Dated dump of the remote (deployed) Neo4j. Stops the DB for the duration of the
## dump (~2-5 min of demo downtime), then restarts it. Dumps are kept on the server.
db-backup:
	@echo "Backing up remote Neo4j (the deployed demo will be briefly unavailable)..."
	@ssh $(SSH_HOST) '\
		mkdir -p $(REMOTE_BACKUP_DIR) && chmod 777 $(REMOTE_BACKUP_DIR); \
		docker stop $(REMOTE_NEO4J_CONTAINER); \
		docker run --rm -v $(REMOTE_NEO4J_VOLUME):/data -v $(REMOTE_BACKUP_DIR):/backups neo4j:5.15.0 \
			neo4j-admin database dump neo4j --to-path=/backups --overwrite-destination=true; \
		RC=$$?; \
		docker start $(REMOTE_NEO4J_CONTAINER); \
		if [ $$RC -ne 0 ]; then echo "DUMP FAILED (db restarted anyway)"; exit $$RC; fi; \
		mv $(REMOTE_BACKUP_DIR)/neo4j.dump $(REMOTE_BACKUP_DIR)/neo4j_$$(date +%Y%m%d_%H%M).dump; \
		ls -lh $(REMOTE_BACKUP_DIR)'
	@echo "Backup done. Remote Neo4j restarted."

## Download the LATEST server dump (runs db-backup first if none exists) and restore
## it into a local Neo4j container on bolt :$(LOCAL_BOLT_PORT) (http :$(LOCAL_HTTP_PORT)).
## Local auth matches the remote password from .env, so only NEO4J_URI changes.
db-pull:
	@LATEST=$$(ssh $(SSH_HOST) "ls -t $(REMOTE_BACKUP_DIR)/neo4j_*.dump 2>/dev/null | head -1"); \
	if [ -z "$$LATEST" ]; then \
		echo "No dump on server — running db-backup first..."; \
		$(MAKE) db-backup; \
		LATEST=$$(ssh $(SSH_HOST) "ls -t $(REMOTE_BACKUP_DIR)/neo4j_*.dump | head -1"); \
	fi; \
	echo "Downloading $$LATEST ..."; \
	mkdir -p $(LOCAL_BACKUP_DIR); \
	scp $(SSH_HOST):$$LATEST $(LOCAL_BACKUP_DIR)/; \
	cp $(LOCAL_BACKUP_DIR)/$$(basename $$LATEST) $(LOCAL_BACKUP_DIR)/neo4j.dump
	@echo "Restoring into local Neo4j..."
	@docker rm -f $(LOCAL_NEO4J_NAME) 2>/dev/null || true
	@docker volume rm $(LOCAL_NEO4J_VOLUME) 2>/dev/null || true
	@docker volume create $(LOCAL_NEO4J_VOLUME) >/dev/null
	@docker run --rm -v $(LOCAL_NEO4J_VOLUME):/data -v $(LOCAL_BACKUP_DIR):/backups neo4j:5.15.0 \
		neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true
	@NEO4J_PASS_VAL=$$(grep '^NEO4J_PASSWORD=' .env | cut -d= -f2-); \
	docker run -d --name $(LOCAL_NEO4J_NAME) \
		-p $(LOCAL_BOLT_PORT):7687 -p $(LOCAL_HTTP_PORT):7474 \
		-e NEO4J_AUTH=neo4j/$$NEO4J_PASS_VAL \
		-e 'NEO4J_PLUGINS=["apoc"]' \
		-e NEO4J_dbms_security_procedures_unrestricted='apoc.*' \
		-e NEO4J_dbms_security_procedures_allowlist='apoc.*' \
		-e NEO4J_server_memory_pagecache_size=1G \
		-e NEO4J_server_memory_heap_initial__size=1G \
		-e NEO4J_server_memory_heap_max__size=2G \
		--memory=4500m \
		-v $(LOCAL_NEO4J_VOLUME):/data \
		neo4j:5.15.0 >/dev/null
	@rm -f $(LOCAL_BACKUP_DIR)/neo4j.dump
	@echo ""
	@echo "Local Neo4j starting on bolt://localhost:$(LOCAL_BOLT_PORT) (browser: http://localhost:$(LOCAL_HTTP_PORT))"
	@echo "Switch the app to it with:   make db-use-local"

## Point the demo backend at the local copy / back at the remote (edits NEO4J_URI in .env).
db-use-local:
	@sed -i.bak 's|^NEO4J_URI=.*|NEO4J_URI=bolt://localhost:$(LOCAL_BOLT_PORT)|' .env
	@echo "NEO4J_URI → bolt://localhost:$(LOCAL_BOLT_PORT) (local copy). Restart make dev to apply."

db-use-remote:
	@sed -i.bak 's|^NEO4J_URI=.*|NEO4J_URI=bolt://localhost:7690|' .env
	@echo "NEO4J_URI → bolt://localhost:7690 (remote via tunnel). Restart make dev to apply."

install: install-backend install-frontend

install-backend:
	@cd $(BACKEND_DIR) && \
	( test -d venv || python3 -m venv venv ) && \
	venv/bin/pip install -r requirements.txt

install-frontend:
	@cd $(FRONTEND_DIR) && npm install

build:
	@cd $(FRONTEND_DIR) && npm run build

## Open the SSH tunnel to the remote demo Neo4j if it is not already up.
## Also detects half-dead tunnels (port listening but connection refused/hung after
## a network change) by probing the bolt port, and reopens them.
tunnel:
	@if lsof -ti tcp:7690 >/dev/null 2>&1; then \
		if nc -z -w 3 localhost 7690 >/dev/null 2>&1; then \
			echo "Tunnel up on :7690."; \
		else \
			echo "Stale tunnel on :7690 (probe failed) — reopening..."; \
			lsof -ti tcp:7690 | xargs kill 2>/dev/null || true; \
			pgrep -f "ssh.*7690:localhost:7687" | xargs kill 2>/dev/null || true; \
			sleep 1; \
			$(TUNNEL_CMD) && echo "Tunnel reopened."; \
		fi; \
	else \
		echo "Opening SSH tunnel: $(TUNNEL_CMD)"; \
		$(TUNNEL_CMD) && echo "Tunnel opened."; \
	fi

## Incremental data update of the demo DB (remote, via tunnel) using the v2 build pipeline:
## refresh deputy/group CSVs, download + ingest new Camera stenografici, atti, roles, embeddings.
## Embeddings hit the v2 cache (build/embeddings_cache.db) so OpenAI cost is near zero for
## sessions already ingested in the v2 DB.
update-data: tunnel
	@test -f $(V2_DIR)/build/build_and_update.py || { \
		echo "ERROR: v2 pipeline not found at $(V2_DIR)/build — set V2_DIR=<path to ParliamentRAG repo>"; exit 1; }
	@test -x $(V2_DIR)/backend/venv/bin/python || { \
		echo "ERROR: v2 backend venv missing — run 'make db-install' inside $(V2_DIR) first"; exit 1; }
	@NEO4J_USER_VAL=$$(grep '^NEO4J_USER=' .env | cut -d= -f2-); \
	NEO4J_PASS_VAL=$$(grep '^NEO4J_PASSWORD=' .env | cut -d= -f2-); \
	test -n "$$NEO4J_PASS_VAL" || { echo "ERROR: NEO4J_PASSWORD not found in .env"; exit 1; }; \
	echo "Updating demo DB at $(DEMO_NEO4J) using pipeline in $(V2_DIR)/build ..."; \
	cd $(V2_DIR) && backend/venv/bin/python build/build_and_update.py update \
		--neo4j-uri $(DEMO_NEO4J) \
		--neo4j-user $${NEO4J_USER_VAL:-neo4j} \
		--neo4j-password $$NEO4J_PASS_VAL
	@echo "Repairing speaker links (v2 ingest attaches new speeches to persona.rdf duplicates)..."
	@$(BACKEND_DIR)/venv/bin/python $(BACKEND_DIR)/scripts/repair_speaker_links.py $(DEMO_NEO4J)
	@echo "Done. The 'Data updated on' date in the sidebar now reflects the DB automatically."
