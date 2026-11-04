#!/usr/bin/env bash
# Paesi e regioni delle statistiche di visita: scarica il file DB-IP «IP to City Lite» del mese (CC BY 4.0) in
# dati/geo/dbip-city-lite.mmdb, se quello che c'è è di un mese prima. Lo chiama pipeline/notte.sh; il servizio web
# legge il file montato in sola lettura e lo riapre da solo quando cambia (api/statistiche.py).
set -euo pipefail
cd "$(dirname "$0")/../.."
DIR=dati/geo
FILE="$DIR/dbip-city-lite.mmdb"
MESE=$(date -u +%Y-%m)
mkdir -p "$DIR"
if [ -f "$DIR/mese" ] && [ "$(cat "$DIR/mese")" = "$MESE" ] && [ -s "$FILE" ]; then
  exit 0
fi
curl -fsSL --retry 3 --max-time 600 "https://download.db-ip.com/free/dbip-city-lite-$MESE.mmdb.gz" | gunzip > "$FILE.nuovo"
[ -s "$FILE.nuovo" ] || { rm -f "$FILE.nuovo"; echo "file DB-IP di $MESE vuoto, tengo quello di prima" >&2; exit 1; }
mv "$FILE.nuovo" "$FILE"
echo "$MESE" > "$DIR/mese"
echo "file DB-IP di $MESE scaricato"
