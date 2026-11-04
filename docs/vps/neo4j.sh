#!/usr/bin/env bash
# Spegne e riaccende Neo4j e il Postgres dell'archivio sulla VPS senza perdere niente: container e dati restano.
# Uso (da root):  neo4j.sh spegni | accendi | stato
# Scelta del 4/11/2026. Vedi README.md.
#
# spegni:  crea il segnale /opt/parliament-rag/neo4j-spento (backup.sh lo legge e salta Neo4j),
#          sposta in /root/cron-sospesi/ i cron che usano o riavviano Neo4j,
#          toglie il riavvio automatico e ferma i container (120 s per chiudere pulito).
# accendi: il contrario, nell'ordine opposto.
# Si può lanciare più volte: ogni passo controlla prima se è già fatto.

set -euo pipefail

# container da spegnere, con la politica di riavvio da rimettere quando si riaccendono (4/11: anche l'archivio)
declare -A POLITICA=([parliament-neo4j-v2]=always [parliament-archivio]=unless-stopped)
CONTAINERS=(parliament-neo4j-v2 parliament-archivio)
SEGNALE=/opt/parliament-rag/neo4j-spento
CRON_DIR=/etc/cron.d
SOSPESI=/root/cron-sospesi
# cron che usano Neo4j o lo riavviano; parliamentrag-backup resta attivo e salta Neo4j col segnale
CRON=(parliamentrag-nightly parliamentrag-report parliamentrag-demo neo4j-bolt-cert)
# processi che non vanno interrotti a metà
IN_CORSO='nightly\.sh|nightly_report\.py|backup\.sh'

dico() { printf '%s\n' "$*"; }
errore() { printf 'errore: %s\n' "$*" >&2; exit 1; }

controlli() {
  [[ $EUID -eq 0 ]] || errore "va lanciato da root"
  command -v docker >/dev/null || errore "docker non trovato"
  local k
  for k in "${CONTAINERS[@]}"; do docker container inspect "$k" >/dev/null 2>&1 || errore "container $k non trovato"; done
}

niente_in_corso() {
  local p
  if p=$(pgrep -af "$IN_CORSO"); then
    [[ ${FORZA:-0} == 1 ]] && { dico "attenzione: processi in corso, continuo perché FORZA=1"; return; }
    errore "processi in corso, riprova quando finiscono (oppure FORZA=1):
$p"
  fi
}

in_esecuzione() { [[ $(docker container inspect -f '{{.State.Running}}' "$1") == true ]]; }
politica() { docker container inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$1"; }

spegni() {
  controlli
  niente_in_corso

  # 1. segnale per backup.sh, prima di tutto: un backup che parte adesso non riaccende Neo4j
  if [[ -e $SEGNALE ]]; then dico "segnale già presente: $SEGNALE"
  else install -d -m 755 "$(dirname "$SEGNALE")"; date -Is > "$SEGNALE"; dico "creato $SEGNALE"; fi

  # 2. cron sospesi
  install -d -m 700 "$SOSPESI"
  local c
  for c in "${CRON[@]}"; do
    if [[ -e $CRON_DIR/$c ]]; then
      [[ -e $SOSPESI/$c ]] && errore "$c c'è sia in $CRON_DIR sia in $SOSPESI: controlla a mano"
      mv "$CRON_DIR/$c" "$SOSPESI/$c"; dico "cron sospeso: $c"
    elif [[ -e $SOSPESI/$c ]]; then dico "cron già sospeso: $c"
    else dico "cron assente, lo salto: $c"; fi
  done

  # 3. niente riavvio automatico, poi stop pulito
  local k
  for k in "${CONTAINERS[@]}"; do
    if [[ $(politica "$k") != no ]]; then docker update --restart=no "$k" >/dev/null; dico "$k: riavvio automatico tolto"
    else dico "$k: riavvio automatico già tolto"; fi
    if in_esecuzione "$k"; then dico "fermo $k (fino a 120 s)…"; docker stop -t 120 "$k" >/dev/null; dico "$k fermato"
    else dico "$k già fermo"; fi
  done

  dico "Neo4j e archivio spenti. Per riaccenderli: $0 accendi"
}

accendi() {
  controlli

  # 1. riavvio automatico e avvio, poi attesa: il controllo di salute del container, se c'è, altrimenti basta che giri
  local k i s
  for k in "${CONTAINERS[@]}"; do
    if [[ $(politica "$k") != "${POLITICA[$k]}" ]]; then docker update --restart="${POLITICA[$k]}" "$k" >/dev/null; dico "$k: riavvio automatico rimesso (${POLITICA[$k]})"
    else dico "$k: riavvio automatico già ${POLITICA[$k]}"; fi
    if in_esecuzione "$k"; then dico "$k già acceso"
    else docker start "$k" >/dev/null; dico "avviato $k"; fi
    for i in $(seq 1 60); do
      s=$(docker container inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$k")
      [[ $s == healthy || $s == running ]] && break
      [[ $s == exited || $s == dead ]] && errore "$k si è fermato: docker logs --tail 50 $k"
      sleep 5
    done
    dico "$k: $s"
    [[ $s == healthy || $s == running ]] || errore "$k non è pronto dopo 5 minuti: docker logs --tail 50 $k"
  done

  # 3. cron ripristinati
  local c
  for c in "${CRON[@]}"; do
    if [[ -e $SOSPESI/$c ]]; then
      [[ -e $CRON_DIR/$c ]] && errore "$c c'è sia in $CRON_DIR sia in $SOSPESI: controlla a mano"
      mv "$SOSPESI/$c" "$CRON_DIR/$c"; chown root:root "$CRON_DIR/$c"; chmod 644 "$CRON_DIR/$c"; dico "cron ripristinato: $c"
    elif [[ -e $CRON_DIR/$c ]]; then dico "cron già attivo: $c"
    else dico "cron assente, lo salto: $c"; fi
  done

  # 4. via il segnale: da stanotte backup.sh torna a fermare e riavviare Neo4j
  if [[ -e $SEGNALE ]]; then rm -f "$SEGNALE"; dico "tolto $SEGNALE"
  else dico "segnale già assente"; fi

  dico "Neo4j e archivio accesi."
}

stato() {
  controlli
  dico "== container"
  local k
  for k in "${CONTAINERS[@]}"; do
    dico "$k: $(docker container inspect -f '{{.State.Status}}' "$k"), riavvio automatico $(politica "$k")"
  done
  dico ""
  dico "== segnale per backup.sh"
  if [[ -e $SEGNALE ]]; then dico "presente ($SEGNALE, dal $(cat "$SEGNALE"))"; else dico "assente: backup.sh gestisce Neo4j come sempre"; fi
  dico ""
  dico "== cron"
  local c
  for c in parliamentrag-backup "${CRON[@]}"; do
    if [[ -e $CRON_DIR/$c ]]; then dico "attivo    $c"
    elif [[ -e $SOSPESI/$c ]]; then dico "sospeso   $c"
    else dico "assente   $c"; fi
  done
}

case "${1:-}" in
  spegni) spegni ;;
  accendi) accendi ;;
  stato) stato ;;
  *) dico "uso: $0 spegni | accendi | stato" >&2; exit 2 ;;
esac
