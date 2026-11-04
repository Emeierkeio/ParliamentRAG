#!/usr/bin/env bash
# Giro notturno per il cron della VPS (orari in UTC, vedi docs/produzione.md):
#   - un giro alla volta: flock sul file notte.lock; se un giro è ancora in corso, questo non parte;
#   - un log per giro, con la data: $LOG_DIR/giro-AAAAMMGG-HHMMSS.log (predefinito dati/log), tenuti 60 giorni;
#   - «python -m pipeline giro» rifiuta il giro se uno completo è riuscito nelle ultime 20 ore (--forza per lanciarlo);
#   - a fine giro, se l'esito non è ok, una mail a segnalazioni@parliamentrag.it (python -m pipeline avvisa, BREVO_API_KEY).
#
#   pipeline/notte.sh [--forza]
set -u

QUI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$QUI" || exit 1
PY="$QUI/.venv/bin/python"
LOG_DIR="${LOG_DIR:-$QUI/dati/log}"
mkdir -p "$LOG_DIR"

exec 9>"$LOG_DIR/notte.lock"
if ! flock -n 9; then
  echo "$(date -u '+%F %T') UTC: un giro è già in corso, non parto" >> "$LOG_DIR/notte.log"
  exit 0
fi

LOG="$LOG_DIR/giro-$(date -u +%Y%m%d-%H%M%S).log"
DAL="$(date +%s)"
echo "$(date -u '+%F %T') UTC: inizio, log in $LOG" >> "$LOG_DIR/notte.log"

"$PY" -m pipeline giro "$@" > "$LOG" 2>&1
USCITA=$?

"$PY" -m pipeline avvisa --dal "$DAL" --uscita "$USCITA" --log "$LOG" >> "$LOG" 2>&1
echo "$(date -u '+%F %T') UTC: fine, uscita $USCITA" >> "$LOG_DIR/notte.log"

find "$LOG_DIR" -name 'giro-*.log' -mtime +60 -delete 2>/dev/null
exit "$USCITA"
