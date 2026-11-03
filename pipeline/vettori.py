"""Vettori per la ricerca per significato: brani degli interventi e text-embedding-3-large a 1.024 dimensioni, sempre
con la Batch API (10-decisioni/2026-11-03-modello-ricerca-significato). Tabelle in schema/v3.sql.

  python -m pipeline.vettori taglia         brani degli interventi nuovi o cambiati
  python -m pipeline.vettori invia [quanti] impronte senza vettore, un batch ogni 2.000 brani (predefinito: 10 batch)
  python -m pipeline.vettori raccogli       scarica i batch finiti e scrive i vettori
  python -m pipeline.vettori stato          conteggi e batch aperti
  python -m pipeline.vettori indice         indice HNSW, da costruire quando i vettori ci sono tutti

Si rilancia senza danni: «invia» salta le impronte già in un batch aperto, «raccogli» salta i vettori già scritti.
Un batch scaduto o fallito libera le sue impronte, che il prossimo «invia» rimanda.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
from array import array

from . import openai_batch as batch
from .ambiente import QUI
from .carica.postgres import _csv, psql

MODELLO = "text-embedding-3-large"
DIMENSIONI = 1024
LUNGHEZZA = 1_500          # come nella prova (benchmark/embedding/brani.py)
MINIMO = 300               # interventi più corti: quasi sempre procedurali, esclusi come nella prova
MASSIMO = 6_000            # una «frase» più lunga (testo senza punteggiatura) si spezza agli spazi: il modello regge ~8.000 token
PER_RICHIESTA = 100
PER_BATCH = 2_000          # la connessione non regge file grandi
PER_GIRO = 20_000          # interventi letti da Postgres per volta
CARTELLA = QUI / "dati" / "vettori"
csv.field_size_limit(sys.maxsize)   # ci sono interventi da oltre 140 mila caratteri

FINE = re.compile(r"[.!?»]\s+(?=[A-ZÀ-Ú«(])")
ABBREVIAZIONI = {"n", "nn", "on", "doc", "art", "artt", "v", "pag", "pagg", "cfr", "lett", "sen", "dott", "prof", "sig"}
SIGLA = re.compile(r"^(?:[A-ZÀ-Ú]\.)+$")       # iniziali e sigle: G., C., S., A.C.
NUMERO = re.compile(r"^\d{1,3}\.$")            # «comma 1.», «n. 12.»; gli anni a quattro cifre chiudono la frase


def _abbreviazione(testo: str, punto: int) -> bool:
    """Il punto in posizione `punto` chiude un'abbreviazione e non la frase."""
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


def taglia_testo(testo: str) -> list[tuple[int, int]]:
    """Brani di circa LUNGHEZZA caratteri, mai a metà frase; un resto sotto MINIMO va col brano prima."""
    if len(testo.strip()) < MINIMO:
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


def _leggi(sql: str) -> list[list[str]]:
    """Righe di una SELECT, via COPY in CSV. In byte e non in testo: subprocess in modo testo tocca gli a capo."""
    cmd = ["docker", "compose", "exec", "-T", "testi", "psql", "-U", "parliamentrag", "-d", "parliamentrag", "-v", "ON_ERROR_STOP=1", "-q",
           "-c", f"COPY ({sql}) TO STDOUT WITH (FORMAT csv)"]
    r = subprocess.run(cmd, cwd=QUI, capture_output=True, timeout=900)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-800:])
    return list(csv.reader(io.StringIO(r.stdout.decode("utf-8"), newline="")))


def taglia() -> dict:
    # brani di interventi spariti o cambiati: via; i loro vettori restano, legati all'impronta
    psql("DELETE FROM passage p WHERE NOT EXISTS (SELECT 1 FROM speech s WHERE s.uri = p.speech AND s.hash = p.speech_hash);")
    ultimo, interventi, brani = "", 0, 0
    while True:
        righe = _leggi(f"""SELECT s.uri, s.hash, s.text FROM speech s
            WHERE s.uri > {_letterale(ultimo)} AND length(s.text) >= {MINIMO}
              AND NOT EXISTS (SELECT 1 FROM passage p WHERE p.speech = s.uri)
            ORDER BY s.uri LIMIT {PER_GIRO}""")
        if not righe:
            break
        nuovi = []
        for uri, h, testo in righe:
            nuovi += [[uri, h, k, a, b, impronta(testo[a:b])] for k, (a, b) in enumerate(taglia_testo(testo))]
        psql("BEGIN;\nCOPY passage (speech, speech_hash, ord, start_char, end_char, hash) FROM STDIN WITH (FORMAT csv);\n"
             f"{_csv(nuovi)}\\.\nCOMMIT;\n")
        ultimo, interventi, brani = righe[-1][0], interventi + len(righe), brani + len(nuovi)
        print(f"taglia: {interventi} interventi, {brani} brani", flush=True)
    return {"interventi": interventi, "brani": brani}


def _letterale(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def invia(quanti: int = 10) -> dict:
    """Fino a `quanti` batch da PER_BATCH brani; ogni brano diverso una volta sola."""
    CARTELLA.mkdir(parents=True, exist_ok=True)
    righe = _leggi(f"""WITH aperte AS (SELECT DISTINCT unnest(hashes) AS hash FROM vector_batch WHERE status = 'inviato')
        SELECT DISTINCT ON (p.hash) p.hash, substr(s.text, p.start_char + 1, p.end_char - p.start_char)
        FROM passage p JOIN speech s ON s.uri = p.speech AND s.hash = p.speech_hash
        WHERE NOT EXISTS (SELECT 1 FROM passage_vector v WHERE v.hash = p.hash AND v.model = '{MODELLO}')
          AND NOT EXISTS (SELECT 1 FROM aperte a WHERE a.hash = p.hash)
        ORDER BY p.hash LIMIT {quanti * PER_BATCH}""")
    inviati = []
    for inizio in range(0, len(righe), PER_BATCH):
        parte = righe[inizio:inizio + PER_BATCH]
        if any(impronta(t) != h for h, t in parte):
            raise RuntimeError("un brano letto da Postgres non torna con la sua impronta")
        f = CARTELLA / f"richieste-{parte[0][0][:12]}.jsonl"
        with open(f, "w", encoding="utf-8") as out:
            for k in range(0, len(parte), PER_RICHIESTA):
                out.write(json.dumps({"custom_id": str(k), "method": "POST", "url": "/v1/embeddings", "body": {
                    "model": MODELLO, "dimensions": DIMENSIONI, "encoding_format": "base64",
                    "input": [t for _, t in parte[k:k + PER_RICHIESTA]]}}, ensure_ascii=False) + "\n")
        bid = batch.invia(f, "/v1/embeddings", f"vettori dei brani ({len(parte)})")
        psql("COPY vector_batch (id, model, status, hashes) FROM STDIN WITH (FORMAT csv);\n"
             f"{_csv([[bid, MODELLO, 'inviato', '{' + ','.join(h for h, _ in parte) + '}']])}\\.\n")
        f.unlink()
        inviati.append(bid)
        print(f"invia: {bid}, {len(parte)} brani", flush=True)
    return {"batch": len(inviati), "brani": len(righe)}


def _vettore(b64: str) -> str:
    v = array("f")
    v.frombytes(base64.b64decode(b64))     # float32 little-endian, come li manda OpenAI (il Mac e Linux x86 sono little-endian)
    if len(v) != DIMENSIONI:
        raise RuntimeError(f"vettore da {len(v)} dimensioni")
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


def raccogli() -> dict:
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
    batch_ = {st: int(n) for st, n in _leggi("SELECT status, count(*) FROM vector_batch GROUP BY status")}
    (token,), = _leggi("SELECT coalesce(sum(tokens), 0) FROM vector_batch")
    return {"brani": int(brani), "impronte": int(impronte), "vettori": int(vettori), "batch": batch_, "token": int(token),
            "spesa_dollari": round(int(token) / 1e6 * 0.065, 2)}   # 0,13 $ per milione di token, metà con la Batch API


def indice() -> dict:
    psql("SET maintenance_work_mem = '2GB';\n"
         "CREATE INDEX IF NOT EXISTS passage_vector_hnsw ON passage_vector USING hnsw (embedding vector_cosine_ops);\n", timeout=6 * 3600)
    return {"indice": "passage_vector_hnsw"}


if __name__ == "__main__":
    comandi = {"taglia": taglia, "invia": invia, "raccogli": raccogli, "stato": stato, "indice": indice}
    if len(sys.argv) < 2 or sys.argv[1] not in comandi:
        sys.exit(__doc__)
    argomenti = [int(x) for x in sys.argv[2:]]
    print(json.dumps(comandi[sys.argv[1]](*argomenti), ensure_ascii=False, indent=1))
