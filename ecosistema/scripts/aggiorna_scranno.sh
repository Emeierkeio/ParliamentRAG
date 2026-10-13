#!/bin/sh
# Rigenera i dati dei deputati di Scranno (conteggi, commissioni, gruppi) dal grafo,
# così sono aggiornati alla stessa data dei numeri del grafo.
# Serve il tunnel SSH verso Neo4j (porta 7690), aperto con `make tunnel` in ricerca/.
# Solo letture: lo script di export di Scranno usa sessioni READ_ACCESS.
set -e
QUI="$(cd "$(dirname "$0")" && pwd)"
RADICE="$QUI/../.."
TMP="$(mktemp -d)"
(cd "$RADICE/ricerca" && make tunnel)
nc -z -w 5 localhost 7690 || { echo "Tunnel non raggiungibile su :7690"; exit 1; }
# Copia dello script di Scranno che scrive in una cartella temporanea, non in scranno/public/data
sed "s#^OUT = ROOT / \"public\" / \"data\"#OUT = Path(\"$TMP\")#" "$RADICE/scranno/scripts/export_data.py" > "$TMP/export_data.py"
(cd "$TMP" && uv run --with neo4j python export_data.py --env "$RADICE/stenografo/apps/api/.env")
python3 "$QUI/build_deputati.py" "$TMP"
echo "Fatto: scranno/deputati.js aggiornato da $TMP"
