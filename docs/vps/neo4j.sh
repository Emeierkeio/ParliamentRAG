#!/usr/bin/env bash
# Spegne e riaccende Neo4j sulla VPS senza perdere niente: il container e i dati restano.
# Uso (da root):  neo4j.sh spegni | accendi | stato
# Decisione del 4/11/2026 (vault/10-decisioni/2026-11-04-tutto-su-vps.md). Vedi README.md.
#
# spegni:  crea il segnale /opt/parliament-rag/neo4j-spento (backup.sh lo legge e salta Neo4j),
#          sposta in /root/cron-sospesi/ i cron che usano o riavviano Neo4j,
#          toglie il riavvio automatico e ferma il container (120 s per chiudere pulito).
# accendi: il contrario, nell'ordine opposto.
# Si può lanciare più volte: ogni passo controlla prima se è già fatto.

set -euo pipefail

CONTAINER=parliament-neo4j-v2
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
  docker container inspect "$CONTAINER" >/dev/null 2>&1 || errore "container $CONTAINER non trovato"
}

niente_in_corso() {
  local p
  if p=$(pgrep -af "$IN_CORSO"); then
    [[ ${FORZA:-0} == 1 ]] && { dico "attenzione: processi in corso, continuo perché FORZA=1"; return; }
    errore "processi in corso, riprova quando finiscono (oppure FORZA=1):
$p"
  fi
}

in_esecuzione() { [[ $(docker container inspect -f '{{.State.Running}}' "$CONTAINER") == true ]]; }
politica() { docker container inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$CONTAINER"; }

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
  if [[ $(politica) != no ]]; then docker update --restart=no "$CONTAINER" >/dev/null; dico "riavvio automatico tolto"
  else dico "riavvio automatico già tolto"; fi
  if in_esecuzione; then dico "fermo $CONTAINER (fino a 120 s)…"; docker stop -t 120 "$CONTAINER" >/dev/null; dico "fermato"
  else dico "$CONTAINER già fermo"; fi

  dico "Neo4j spento. Per riaccenderlo: $0 accendi"
}

accendi() {
  controlli

  # 1. riavvio automatico e avvio
  if [[ $(politica) != always ]]; then docker update --restart=always "$CONTAINER" >/dev/null; dico "riavvio automatico rimesso (always)"
  else dico "riavvio automatico già always"; fi
  if in_esecuzione; then dico "$CONTAINER già acceso"
  else docker start "$CONTAINER" >/dev/null; dico "avviato $CONTAINER"; fi

  # 2. attesa: il controllo di salute del container, se c'è, altrimenti basta che giri
  local i s
  for i in $(seq 1 60); do
    s=$(docker container inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$CONTAINER")
    [[ $s == healthy || $s == running ]] && break
    [[ $s == exited || $s == dead ]] && errore "$CONTAINER si è fermato: docker logs --tail 50 $CONTAINER"
    sleep 5
  done
  dico "stato del container: $s"
  [[ $s == healthy || $s == running ]] || errore "$CONTAINER non è pronto dopo 5 minuti: docker logs --tail 50 $CONTAINER"

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

  dico "Neo4j acceso."
}

stato() {
  controlli
  dico "== container"
  docker ps -a --filter "name=^/${CONTAINER}$" --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
  dico "riavvio automatico: $(politica)"
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
