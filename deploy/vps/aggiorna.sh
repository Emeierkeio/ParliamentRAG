#!/usr/bin/env bash
# Aggiorna il servizio web sulla VPS dal ramo del repo: pull, nuova immagine, riavvio, controllo di salute.
# Uso: deploy/vps/aggiorna.sh   (dalla cartella del repo). Il database non si riavvia.
set -euo pipefail
cd "$(dirname "$0")/../.."
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.vps.yml)
prima=$(git rev-parse --short HEAD)
git pull --ff-only
dopo=$(git rev-parse --short HEAD)
"${COMPOSE[@]}" up -d --build web caddy
# il Caddyfile è montato come file: git pull lo sostituisce e Caddy vedrebbe ancora quello vecchio
if ! git diff --quiet "$prima" "$dopo" -- deploy/vps/Caddyfile; then "${COMPOSE[@]}" restart caddy; fi
for i in $(seq 1 30); do
	if "${COMPOSE[@]}" exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/salute', timeout=4)" 2>/dev/null; then
		echo "aggiornato $prima -> $dopo, il servizio risponde"
		exit 0
	fi
	sleep 2
done
echo "il servizio non risponde dopo l'aggiornamento $prima -> $dopo: torna indietro con git checkout $prima e rilancia" >&2
exit 1
