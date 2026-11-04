# Neo4j sulla VPS: spegnere e riaccendere

Con il servizio unico sulla VPS Neo4j non serve più, ma deve potersi riaccendere subito
(scelta del 4/11/2026). `neo4j.sh`
lo spegne senza toccare container e dati.

```sh
scp docs/vps/neo4j.sh root@<vps>:/root/neo4j.sh
ssh root@<vps> 'chmod 700 /root/neo4j.sh && /root/neo4j.sh stato'
```

| Comando | Cosa fa |
|---|---|
| `neo4j.sh stato` | container, politica di riavvio, segnale per il backup, cron attivi e sospesi |
| `neo4j.sh spegni` | crea `/opt/parliament-rag/neo4j-spento`; sposta in `/root/cron-sospesi/` i cron `parliamentrag-nightly`, `parliamentrag-report`, `parliamentrag-demo`, `neo4j-bolt-cert`; `docker update --restart=no`; `docker stop -t 120` |
| `neo4j.sh accendi` | `--restart=always`, `docker start`, attende che il container sia pronto, rimette i cron in `/etc/cron.d/`, toglie il segnale |

Lo script si ferma al primo errore e si può rilanciare: ogni passo controlla se è già
fatto. Non parte se è in corso `nightly.sh`, `nightly_report.py` o `backup.sh`
(si forza con `FORZA=1`).

## Prima di spegnere: backup.sh

`/etc/cron.d/parliamentrag-backup` resta attivo, perché fa anche il backup di Postgres.
Ma `/opt/parliamentrag-backup/backup.sh` ferma e riavvia Neo4j per il dump: con Neo4j
spento lo riaccenderebbe. Va modificato a mano, una volta, prima del primo `spegni`.

Nel blocco Neo4j (quello con `docker stop` e `docker start`) aggiungi il controllo del
segnale in testa alla condizione dell'`if`. Con la versione di `backup.sh` in uso sulla VPS la riga diventa:

```bash
if [ ! -e /opt/parliament-rag/neo4j-spento ] && { [ "$(date -u +%u)" = 7 ] || [ "${1:-}" = "--neo4j" ]; }; then
```

Se nel file installato il blocco non ha un `if`, avvolgilo in
`if [ ! -e /opt/parliament-rag/neo4j-spento ]; then … fi`. Poi prova con
`bash -n /opt/parliamentrag-backup/backup.sh`. Il backup su restic continua a
conservare l'ultimo dump di Neo4j.

## Da sapere

- `accendi` rimette anche `parliamentrag-demo`, che è scaduto: se non serve, cancellalo
  da `/etc/cron.d/` dopo l'accensione.
- Con Caddy sulla porta 80 il rinnovo di certbot per db.parliamentrag.it non funziona più
  (vedi la decisione del 4/11). Se Neo4j resta acceso a lungo, il certificato TLS di Bolt
  va rinnovato in un altro modo.
- Il ripristino del dump di Postgres sulla VPS va fatto con Neo4j spento, perché la
  ricostruzione dell'indice HNSW è il momento di picco della memoria.
