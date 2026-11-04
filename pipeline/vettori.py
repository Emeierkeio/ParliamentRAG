"""Vettori per la ricerca per significato: brani dei testi del database e text-embedding-3-large a 1.024 dimensioni,
sempre con la Batch API (scelta del modello: README, «Semantic retrieval»). Tabelle in schema/v3.sql, fonti in FONTI.

  python -m pipeline.vettori taglia [fonte] brani dei testi nuovi o cambiati, di tutte le fonti o di una
  python -m pipeline.vettori invia [quanti] impronte senza vettore, un batch ogni 2.000 brani (predefinito: 10 batch)
  python -m pipeline.vettori raccogli       scarica i batch finiti e scrive i vettori
  python -m pipeline.vettori stato          conteggi e batch aperti
  python -m pipeline.vettori indice         indice HNSW, da costruire quando i vettori ci sono tutti

Si rilancia senza danni: «invia» salta le impronte già in un batch aperto, «raccogli» salta i vettori già scritti.
Un batch scaduto o fallito libera le sue impronte, che il prossimo «invia» rimanda.

«invia» scrive la riga del batch (stato «in_invio») prima di crearlo su OpenAI e la completa con l'id dopo: se il
processo muore in mezzo, «raccogli» ritrova il batch dai suoi metadati invece di pagarlo due volte. Ogni notte
«invia» non supera `[vettori] dollari_per_notte` di pipeline.toml (stima dai caratteri, contando i batch delle 24 ore prima).
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import sys
import time
import tomllib
import uuid
from array import array
from pathlib import Path

from . import openai_batch as batch
from .ambiente import QUI
from .carica.postgres import _csv, leggi_csv, psql

MODELLO = "text-embedding-3-large"
DIMENSIONI = 1024
LUNGHEZZA = 1_500          # come nella prova (benchmark/embedding/brani.py)
MINIMO = 300               # un resto più corto va col brano prima
MASSIMO = 6_000            # una «frase» più lunga (testo senza punteggiatura) si spezza agli spazi: il modello regge ~8.000 token
PER_RICHIESTA = 100
PER_BATCH = 2_000          # la connessione non regge file grandi
PER_GIRO = 20_000          # testi letti da Postgres per volta
DOLLARI_PER_MILIONE = 0.065   # text-embedding-3-large con la Batch API: metà di 0,13 $ per milione di token
CARATTERI_PER_TOKEN = 3.5     # stima prudente per l'italiano
csv.field_size_limit(sys.maxsize)   # ci sono interventi da oltre 140 mila caratteri

# fonte -> tabella, chiave, testo, impronta del testo, quali righe, lunghezza minima del testo. In ordine di invio:
# prima quello che serve all'autorevolezza (interventi, atti, persone, organi), poi il resto.
FONTI = {
    # sotto i 300 caratteri quasi sempre procedurali, esclusi come nella prova
    "speech": ("speech", "uri", "text", "hash", "true", 300),
    # interrogazioni, mozioni, risoluzioni: conta il testo, il titolo è un'etichetta uguale per tutte
    "act": ("act", "uri", "text", "md5(text)", "text IS NOT NULL", 50),
    # progetti di legge: il titolo dice di cosa parlano
    "act_title": ("act", "uri", "title", "md5(title)", "kind = 'bill' AND title IS NOT NULL", 1),
    "profession": ("person", "uri", "profession", "md5(profession)", "profession IS NOT NULL", 1),
    "education": ("person", "uri", "education", "md5(education)", "education IS NOT NULL", 1),
    "body": ("body", "uri", "name", "md5(name)", "name IS NOT NULL", 1),
    "act_text": ("act_text", "code", "text", "md5(text)", "text IS NOT NULL", 50),
    "document": ("document", "uri", "text", "md5(text)", "text IS NOT NULL", 50),
    "amendment": ("amendment", "uri", "text", "md5(text)", "text IS NOT NULL", 50),
}

FINE = re.compile(r"[.!?»]\s+(?=[A-ZÀ-Ú«(])")
ABBREVIAZIONI = {"n", "nn", "on", "doc", "art", "artt", "v", "pag", "pagg", "cfr", "lett", "sen", "dott", "prof", "sig"}
SIGLA = re.compile(r"^(?:[A-ZÀ-Ú]\.)+$")       # iniziali e sigle: G., C., S., A.C.
NUMERO = re.compile(r"^\d{1,3}\.$")            # «comma 1.», «n. 12.»; gli anni a quattro cifre chiudono la frase


def _abbreviazione(testo: str, punto: int) -> bool:
    """Vero se il punto in posizione `punto` chiude un'abbreviazione: lì la frase continua."""
    inizio = testo.rfind(" ", 0, punto) + 1
    parola = re.split(r"['’]", testo[inizio:punto + 1].lstrip("(«\""))[-1]   # «dell'on.», «dall'art.»
    return parola[:-1].lower() in ABBREVIAZIONI or bool(SIGLA.match(parola)) or bool(NUMERO.match(parola))


def _frasi(testo: str) -> list[tuple[int, int]]:
    """Inizio e fine di ogni frase, spazi esclusi."""
    tagli = [m.end() for m in FINE.finditer(testo) if not (testo[m.start()] == "." and _abbreviazione(testo, m.start()))]
    frasi = []
    for a, b in zip([0] + tagli, tagli + [len(testo)]):
        while a < b and testo[a].isspace():
            a += 1
        while b > a and testo[b - 1].isspace():
            b -= 1
        if b > a:
            frasi += _spezza(testo, a, b)
    return frasi


def _spezza(testo: str, a: int, b: int) -> list[tuple[int, int]]:
    if b - a <= MASSIMO:
        return [(a, b)]
    pezzi = []
    while b - a > LUNGHEZZA:
        c = testo.rfind(" ", a, a + LUNGHEZZA)
        c = c if c > a else a + LUNGHEZZA
        pezzi.append((a, c))
        a = c + 1 if testo[c:c + 1] == " " else c
    return pezzi + [(a, b)] if b > a else pezzi


def taglia_testo(testo: str, minimo: int = MINIMO) -> list[tuple[int, int]]:
    """Brani di circa LUNGHEZZA caratteri, mai a metà frase; un resto sotto MINIMO va col brano prima.
    Un testo più corto di `minimo` non dà brani."""
    if len(testo.strip()) < max(minimo, 1):
        return []
    brani: list[list[int]] = []
    for a, b in _frasi(testo):
        if brani and b - brani[-1][0] <= LUNGHEZZA:
            brani[-1][1] = b
        else:
            brani.append([a, b])
    if len(brani) > 1 and brani[-1][1] - brani[-1][0] < MINIMO:
        resto = brani.pop()
        brani[-1][1] = resto[1]
    return [(a, b) for a, b in brani]


def impronta(testo: str) -> str:
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()


def _config() -> dict:
    return tomllib.loads((QUI / "pipeline.toml").read_text())


def _cartella(config: dict | None = None) -> Path:
    """La cartella dei file di richiesta: `vettori/` dentro la cartella dei dati di pipeline.toml."""
    config = config or _config()
    return (QUI / config["giro"]["cartella_dati"]).resolve() / "vettori"


def _leggi(sql: str) -> list[list[str]]:
    return leggi_csv(sql)


def taglia(solo: str | None = None) -> dict:
    fuori = {}
    for fonte, (tabella, chiave, campo, impronta_sql, filtro, minimo) in FONTI.items():
        if solo and fonte != solo:
            continue
        # brani di testi spariti o cambiati: via; i loro vettori restano, legati all'impronta
        psql(f"""DELETE FROM passage p WHERE p.source = '{fonte}' AND NOT EXISTS (SELECT 1 FROM {tabella} f
                 WHERE f.{chiave} = p.uri AND {filtro} AND {impronta_sql} = p.source_hash);""")
        ultimo, testi, brani = "", 0, 0
        while True:
            righe = _leggi(f"""SELECT {chiave}, {impronta_sql}, {campo} FROM {tabella} f
                WHERE {chiave} > {_letterale(ultimo)} AND {filtro} AND length({campo}) >= {minimo}
                  AND NOT EXISTS (SELECT 1 FROM passage p WHERE p.source = '{fonte}' AND p.uri = f.{chiave})
                ORDER BY {chiave} LIMIT {PER_GIRO}""")
            if not righe:
                break
            nuovi = []
            for uri, h, testo in righe:
                nuovi += [[fonte, uri, h, k, a, b, impronta(testo[a:b])] for k, (a, b) in enumerate(taglia_testo(testo, minimo))]
            psql("BEGIN;\nCOPY passage (source, uri, source_hash, ord, start_char, end_char, hash) FROM STDIN WITH (FORMAT csv);\n"
                 f"{_csv(nuovi)}\\.\nCOMMIT;\n")
            ultimo, testi, brani = righe[-1][0], testi + len(righe), brani + len(nuovi)
            print(f"taglia {fonte}: {testi} testi, {brani} brani", flush=True)
        fuori[fonte] = {"testi": testi, "brani": brani}
    return fuori


def _letterale(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def spesa_recente(ore: float = 24) -> float:
    """Dollari stimati dei batch inviati nelle ultime `ore` ore (dai caratteri dei loro brani)."""
    (caratteri,), = _leggi(f"""SELECT coalesce(sum(p.end_char - p.start_char), 0) FROM (SELECT DISTINCT unnest(hashes) AS hash
        FROM vector_batch WHERE sent_at > now() - interval '{float(ore)} hours') b
        JOIN LATERAL (SELECT start_char, end_char FROM passage WHERE hash = b.hash LIMIT 1) p ON true""")
    return stima_dollari(int(caratteri))


def stima_dollari(caratteri: int) -> float:
    return caratteri / CARATTERI_PER_TOKEN / 1e6 * DOLLARI_PER_MILIONE


def invia(quanti: int = 10, cartella: Path | None = None, tetto_dollari: float | None = None) -> dict:
    """Fino a `quanti` batch da PER_BATCH brani; ogni brano diverso una volta sola; non oltre `tetto_dollari` in 24 ore."""
    config = _config()
    cartella = cartella or _cartella(config)
    cartella.mkdir(parents=True, exist_ok=True)
    if tetto_dollari is None:
        tetto_dollari = float(config.get("vettori", {}).get("dollari_per_notte", 5))
    speso = spesa_recente()
    righe, viste = [], set()
    for fonte, (tabella, chiave, campo, *_) in FONTI.items():   # una fonte alla volta, nell'ordine di FONTI
        if len(righe) >= quanti * PER_BATCH:
            break
        for h, t in _leggi(f"""WITH aperte AS (SELECT DISTINCT unnest(hashes) AS hash FROM vector_batch WHERE status IN ('inviato', 'in_invio'))
            SELECT DISTINCT ON (p.hash) p.hash, substr(f.{campo}, p.start_char + 1, p.end_char - p.start_char)
            FROM passage p JOIN {tabella} f ON f.{chiave} = p.uri
            WHERE p.source = '{fonte}'
              AND NOT EXISTS (SELECT 1 FROM passage_vector v WHERE v.hash = p.hash AND v.model = '{MODELLO}')
              AND NOT EXISTS (SELECT 1 FROM aperte a WHERE a.hash = p.hash)
            ORDER BY p.hash LIMIT {quanti * PER_BATCH - len(righe)}"""):
            if h not in viste:              # lo stesso brano in due fonti (un intervento citato in un documento)
                viste.add(h)
                righe.append((h, t))
    inviati, fermo, brani = [], "", 0
    for inizio in range(0, len(righe), PER_BATCH):
        parte = righe[inizio:inizio + PER_BATCH]
        costo = stima_dollari(sum(len(t) for _, t in parte))
        if speso + costo > tetto_dollari:
            fermo = f"tetto di {tetto_dollari} $ in 24 ore: {speso:.2f} $ già inviati, il batch dopo ne costerebbe {costo:.2f}"
            break
        if any(impronta(t) != h for h, t in parte):   # il testo è cambiato dopo «taglia»: rilanciare «taglia»
            raise RuntimeError("un brano letto da Postgres non torna con la sua impronta")
        f = cartella / f"richieste-{parte[0][0][:12]}.jsonl"
        with open(f, "w", encoding="utf-8") as out:
            for k in range(0, len(parte), PER_RICHIESTA):
                out.write(json.dumps({"custom_id": str(k), "method": "POST", "url": "/v1/embeddings", "body": {
                    "model": MODELLO, "dimensions": DIMENSIONI, "encoding_format": "base64",
                    "input": [t for _, t in parte[k:k + PER_RICHIESTA]]}}, ensure_ascii=False) + "\n")
        riga = f"in_invio-{uuid.uuid4().hex}"           # prima la riga, poi il batch: un crollo in mezzo non lo perde
        psql("COPY vector_batch (id, model, status, hashes) FROM STDIN WITH (FORMAT csv);\n"
             f"{_csv([[riga, MODELLO, 'in_invio', '{' + ','.join(h for h, _ in parte) + '}']])}\\.\n")
        bid = batch.invia(f, "/v1/embeddings", f"vettori dei brani ({len(parte)})", {"riga": riga})
        psql(f"UPDATE vector_batch SET id = {_letterale(bid)}, status = 'inviato' WHERE id = {_letterale(riga)};\n")
        f.unlink()
        speso += costo
        brani += len(parte)
        inviati.append(bid)
        print(f"invia: {bid}, {len(parte)} brani, circa {costo:.2f} $", flush=True)
    r = {"batch": len(inviati), "brani": brani, "dollari_24_ore": round(speso, 2)}
    return {**r, "avviso": fermo} if fermo else r


def ritrova_in_invio(ore_perso: float = 6) -> dict:
    """Righe rimaste «in_invio» (il processo è morto fra la riga e la risposta di OpenAI): se il batch c'è, prende il suo
    id dai metadati; se non c'è dopo `ore_perso` ore, la riga diventa «perso» e le sue impronte tornano libere."""
    righe = _leggi("SELECT id, extract(epoch FROM sent_at) FROM vector_batch WHERE status = 'in_invio'")
    if not righe:
        return {"ritrovati": 0, "persi": 0}
    per_riga = {(b.get("metadata") or {}).get("riga"): b["id"] for b in batch.elenco()}
    ritrovati = persi = 0
    for riga, inviato in righe:
        if riga in per_riga:
            psql(f"UPDATE vector_batch SET id = {_letterale(per_riga[riga])}, status = 'inviato' WHERE id = {_letterale(riga)};\n")
            ritrovati += 1
        elif time.time() - float(inviato) > ore_perso * 3600:
            psql(f"UPDATE vector_batch SET status = 'perso', error = 'invio interrotto, batch non trovato su OpenAI' WHERE id = {_letterale(riga)};\n")
            persi += 1
    return {"ritrovati": ritrovati, "persi": persi}


def _vettore(b64: str) -> str:
    v = array("f")
    v.frombytes(base64.b64decode(b64))     # float32 little-endian, come li manda OpenAI (il Mac e Linux x86 sono little-endian)
    if len(v) != DIMENSIONI:
        raise RuntimeError(f"vettore da {len(v)} dimensioni")
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


def raccogli() -> dict:
    ritrova_in_invio()
    aperti = _leggi("SELECT id, array_to_string(hashes, ',') FROM vector_batch WHERE status = 'inviato' ORDER BY sent_at")
    scritti, ancora = 0, 0
    for bid, hashes in aperti:
        s = batch.stato(bid)
        if s["status"] not in ("completed", "failed", "expired", "cancelled"):
            ancora += 1
            continue
        hashes = hashes.split(",")
        righe, token, errori = [], 0, set()
        for cid, corpo in batch.risultati(s).items():   # anche un batch scaduto può avere risposte buone
            if "data" not in corpo:
                errori.add(json.dumps(corpo.get("errore") or corpo.get("error"), ensure_ascii=False)[:300])
                continue
            token += (corpo.get("usage") or {}).get("total_tokens", 0)
            righe += [[hashes[int(cid) + d["index"]], MODELLO, _vettore(d["embedding"])] for d in corpo["data"]]
        errore = None
        if s["status"] != "completed" or errori:
            errore = "; ".join(sorted(errori)) or json.dumps(s.get("errors"), ensure_ascii=False)[:300]
        psql("BEGIN;\nCREATE TEMP TABLE v (LIKE passage_vector) ON COMMIT DROP;\n"
             f"COPY v FROM STDIN WITH (FORMAT csv);\n{_csv(righe)}\\.\n"
             "INSERT INTO passage_vector SELECT * FROM v ON CONFLICT DO NOTHING;\n"
             f"UPDATE vector_batch SET status = {_letterale(s['status'])}, collected_at = now(), tokens = {token}, "
             f"error = {_letterale(errore) if errore else 'NULL'} WHERE id = {_letterale(bid)};\nCOMMIT;\n")
        scritti += len(righe)
        print(f"raccogli: {bid} {s['status']}, {len(righe)} vettori, {token} token", flush=True)
    return {"vettori": scritti, "batch_ancora_aperti": ancora}


def stato() -> dict:
    (brani, impronte, vettori), = _leggi(f"""SELECT (SELECT count(*) FROM passage), (SELECT count(DISTINCT hash) FROM passage),
        (SELECT count(*) FROM passage_vector WHERE model = '{MODELLO}')""")
    per_fonte = {f: {"brani": int(n), "senza_vettore": int(m)} for f, n, m in _leggi(f"""SELECT p.source, count(*),
        count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM passage_vector v WHERE v.hash = p.hash AND v.model = '{MODELLO}'))
        FROM passage p GROUP BY 1 ORDER BY 1""")}
    batch_ = {st: int(n) for st, n in _leggi("SELECT status, count(*) FROM vector_batch GROUP BY status")}
    (token,), = _leggi("SELECT coalesce(sum(tokens), 0) FROM vector_batch")
    return {"brani": int(brani), "impronte": int(impronte), "vettori": int(vettori), "per_fonte": per_fonte, "batch": batch_, "token": int(token),
            "spesa_dollari": round(int(token) / 1e6 * 0.065, 2)}   # 0,13 $ per milione di token, metà con la Batch API


def indice() -> dict:
    # senza processi paralleli: in Docker la memoria condivisa (/dev/shm) è di 64 MB e la costruzione parallela non ci sta
    psql("SET maintenance_work_mem = '2GB';\nSET max_parallel_maintenance_workers = 0;\n"
         "CREATE INDEX IF NOT EXISTS passage_vector_hnsw ON passage_vector USING hnsw (embedding halfvec_cosine_ops);\n", timeout=6 * 3600)
    return {"indice": "passage_vector_hnsw"}


def controlla_indice() -> dict:
    """L'indice HNSW c'è ed è valido? Senza, la ricerca per significato legge tutti i vettori (secondi per domanda)."""
    r = _leggi("""SELECT i.indisvalid FROM pg_class c JOIN pg_index i ON i.indexrelid = c.oid WHERE c.relname = 'passage_vector_hnsw'""")
    if not r:
        raise RuntimeError("manca l'indice passage_vector_hnsw: python -m pipeline.vettori indice")
    if r[0][0] != "t":
        raise RuntimeError("l'indice passage_vector_hnsw non è valido (costruzione interrotta?): va rifatto")
    return {"indice": "passage_vector_hnsw", "valido": True}


# passi del giro notturno (passi.py): si raccolgono i batch della notte prima, si tagliano i testi caricati, si inviano i brani nuovi
def passo_raccogli(ctx) -> dict:
    return raccogli()


def passo_taglia(ctx) -> dict:
    return taglia()


def passo_invia(ctx) -> dict:
    return invia(50, ctx.cartella / "vettori", float(ctx.config.get("vettori", {}).get("dollari_per_notte", 5)))


def passo_controlla_indice(ctx) -> dict:
    return controlla_indice()


if __name__ == "__main__":
    comandi = {"taglia": taglia, "invia": invia, "raccogli": raccogli, "stato": stato, "indice": indice, "controlla": controlla_indice}
    if len(sys.argv) < 2 or sys.argv[1] not in comandi:
        sys.exit(__doc__)
    argomenti = [x if sys.argv[1] == "taglia" else int(x) for x in sys.argv[2:]]
    print(json.dumps(comandi[sys.argv[1]](*argomenti), ensure_ascii=False, indent=1))
