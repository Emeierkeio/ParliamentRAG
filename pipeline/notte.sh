#!/usr/bin/env bash
# Giro notturno per il cron della VPS (orari in UTC, vedi docs/produzione.md):
#   - un giro alla volta: flock sul file notte.lock; se un giro è ancora in corso, questo non parte;
#   - un log per giro, con la data: $LOG_DIR/giro-AAAAMMGG-HHMMSS.log (predefinito dati/log), tenuti 60 giorni;
#   - «python -m pipeline giro» rifiuta il giro se uno completo è riuscito nelle ultime 20 ore (--forza per lanciarlo);
#   - prima del giro, il file DB-IP dei paesi del mese (deploy/vps/geoip.sh), per le statistiche di visita;
#   - a fine giro, se l'esito non è ok, una mail a segnalazioni@parliamentrag.it (python -m pipeline avvisa, BREVO_API_KEY);
#   - se il giro è riuscito, le tabelle su Hugging Face e, il primo del mese, la bozza della nuova versione su Zenodo
#     (python -m pipeline esporta, HF_TOKEN e ZENODO_TOKEN): un export non riuscito resta nel log e non cambia l'uscita.
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

# paesi e regioni delle statistiche: il file DB-IP del mese, se manca (non ferma il giro)
"$QUI/deploy/vps/geoip.sh" >> "$LOG" 2>&1 || echo "file DB-IP non aggiornato" >> "$LOG"

"$PY" -m pipeline giro "$@" >> "$LOG" 2>&1
USCITA=$?

if [ "$USCITA" -eq 0 ]; then
  ESPORTA=(--hf)
  [ "$(date -u +%d)" = "01" ] && ESPORTA+=(--zenodo)
  "$PY" -m pipeline esporta "${ESPORTA[@]}" >> "$LOG" 2>&1 || echo "export non riuscito (python -m pipeline esporta ${ESPORTA[*]})" >> "$LOG"
fi

"$PY" -m pipeline avvisa --dal "$DAL" --uscita "$USCITA" --log "$LOG" >> "$LOG" 2>&1
echo "$(date -u '+%F %T') UTC: fine, uscita $USCITA" >> "$LOG_DIR/notte.log"

find "$LOG_DIR" -name 'giro-*.log' -mtime +60 -delete 2>/dev/null
exit "$USCITA"
