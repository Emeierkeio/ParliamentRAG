"""Converte i fascicoli salvati da Fascicoli nel formato verificabile v1.

Legge i nodi ChatHistory del grafo in sola lettura e scrive un file JSON per
risposta. Riproducibile: stesso grafo, stessi file.

    NEO4J_URI=… NEO4J_USER=… NEO4J_PASSWORD=… \\
        python tests/fixtures/converti_fascicoli.py --fino-a 2026-08-06 --quante 20

Come si costruisce ogni citazione, da quello che il lettore vede:

- quote: il testo tra «» nel fascicolo, nella forma
  [«…»](leg19_sed15_tit00070.sub00020.int00020_chunk_4), come appare a chi legge;
- speech: il link della citazione punta a un chunk. L'ID del chunk è l'ID
  dell'intervento più `_chunk_N` (Chunk.id = Speech.id + "_chunk_" + indice):
  togliendo il suffisso si ottiene lo speech_id del dataset. Il chunk è un
  tratto del testo integrale dell'intervento (misura del 16/10/2026: 174.760
  chunk su 174.760, sottostringhe esatte);
- speaker: la persona che il fascicolo nomina (nome e cognome salvati nella
  citazione), cercata per nome tra le persone del grafo; tra omonimi si
  sceglie chi ha davvero parlato, se è tra loro;
- group: il gruppo che il fascicolo indica nella citazione, tradotto nell'URI
  ufficiale con la tabella verifica/gruppi_ufficiali.json; «Governo» diventa
  government: true. Per il Misto il fascicolo salva solo «Misto»: se la
  sezione, prima della citazione, nomina una componente («la componente
  +Europa»), si usa l'URI dell'ultima nominata, come la legge chi legge;
  altrimenti resta Misto;
- link: l'URL salvato con la citazione, se c'è (Senato); altrimenti quello che
  Fascicoli costruisce dall'ID (frontend/src/lib/official-links.ts,
  officialSpeechUrl), cioè il link su cui il lettore clicca.

- question: una domanda scritta da noi, da domande.json, mai quella dell'utente;
  il testo del fascicolo non viene copiato (il campo text è facoltativo).

La scelta delle risposte non guarda gli esiti: le più recenti le cui
citazioni cadono tutte nella copertura dei dati pubblicati (camere e date).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))

from verifica import identificatori as ids  # noqa: E402

SCHEMA = "https://w3id.org/parliamentrag/verify/v1"
# Le domande scritte dagli utenti non escono dal grafo: ogni risposta di prova
# prende una domanda scritta da noi sullo stesso tema (domande.json). Per lo
# stesso motivo il testo del fascicolo non viene copiato.
DOMANDE = Path(__file__).with_name("domande.json")
DOMANDA_ASSENTE = "Domanda non pubblicata"
SENATE_SITTINGS_URL = "https://www.senato.it/lavori/assemblea/resoconti-elenco-cronologico"
_CITAZIONE = re.compile(r"\[«(.+?)»\]\(([^)\s]+)\)", re.S)


def _piega(s: str) -> str:
    s = re.sub(r"([AEIOUaeiou])'(?=\s|$)", r"\1", s or "")  # BONAFE' -> BONAFE
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return " ".join(s.lower().replace("'", " ").split())


def leggi(driver):
    with driver.session(default_access_mode="READ") as s:
        fascicoli = [r.data() for r in s.run(
            "MATCH (c:ChatHistory) RETURN c.id AS id, c.answer AS answer, "
            "c.timestamp AS timestamp, c.citations AS citations, c.scope AS scope, "
            "c.topic_stats AS topic_stats ORDER BY c.timestamp DESC")]
        persone = [r.data() for r in s.run(
            "MATCH (p:Person) RETURN p.id AS id, p.first_name AS first, p.last_name AS last")]
        componenti = [r.data() for r in s.run(
            "MATCH (c:MistoComponent) RETURN c.uri AS uri, c.name AS name, coalesce(c.chamber, 'camera') AS chamber")]
        speech_ids = sorted({ids.da_chunk(t) for f in fascicoli for _, t in _CITAZIONE.findall(f["answer"] or "")})
        interventi = {r["id"]: r for r in (x.data() for x in s.run(
            "UNWIND $ids AS sid MATCH (i:Speech {id: sid}) "
            "OPTIONAL MATCH (i)-[:SPOKEN_BY]->(p:Person) "
            "OPTIONAL MATCH (i)<-[:CONTAINS_SPEECH]-(:Phase)<-[:HAS_PHASE]-(:Debate)<-[:HAS_DEBATE]-(s:Session) "
            "RETURN i.id AS id, p.id AS speaker, toString(s.date) AS date", ids=speech_ids))}
    return fascicoli, persone, interventi, componenti


def _componente(prima: str, camera: str, componenti: list):
    """L'ultima componente del Misto nominata prima della citazione, nella sua sezione."""
    testo = ids.chiave_nome(prima)
    posizioni = {}
    for c in componenti:
        if c["chamber"] == camera:
            i = testo.rfind(ids.chiave_nome(c["name"]))
            if i >= 0:
                posizioni[c["uri"]] = i
    return max(posizioni, key=posizioni.get) if posizioni else None


def converti(f: dict, per_nome: dict, interventi: dict, componenti: list, domande: dict) -> tuple[dict, list]:
    citazioni = json.loads(f["citations"] or "[]")
    per_chunk = {c.get("chunk_id"): c for c in citazioni}
    per_speech = {}
    for c in citazioni:
        per_speech.setdefault(c.get("intervention_id"), c)
    claims, problemi = [], []
    for n, (quote, target) in enumerate(_CITAZIONE.findall(f["answer"] or ""), start=1):
        speech = ids.da_chunk(target)
        c = per_chunk.get(target) or per_speech.get(speech)
        if c is None:
            problemi.append(f"citazione {n}: nessun record per {target}")
            continue
        nome = _piega(f"{c.get('deputy_first_name', '')} {c.get('deputy_last_name', '')}")
        candidati = per_nome.get(nome, [])
        vero = (interventi.get(speech) or {}).get("speaker")
        if not candidati:
            # Nome mostrato accorciato («Maria Elisabetta Alberti» per Alberti Casellati)
            candidati = sorted({i for k, v in per_nome.items() if k.startswith(nome + " ") for i in v})
        if vero in candidati:
            speaker = vero
        elif len(candidati) == 1:
            speaker = candidati[0]
        else:
            problemi.append(f"citazione {n}: persona {nome!r} non trovata ({len(candidati)} candidati)")
            continue
        camera = "senato" if speech.startswith("sen_") else "camera"
        claim = {"id": f"{n}", "speaker": speaker}
        etichetta = c.get("group") or ""
        if etichetta == "Governo":
            claim["government"] = True
        else:
            gruppo = ids.uri_gruppo(etichetta, camera) or ids.uri_gruppo(etichetta)
            if gruppo and ids.e_il_misto(gruppo):
                testo = f["answer"] or ""
                fine = testo.find(f"]({target})")
                sezione = testo[testo.rfind("\n#", 0, fine) + 1:fine]
                gruppo = _componente(sezione, camera, componenti) or gruppo
            if not gruppo:
                problemi.append(f"citazione {n}: gruppo {etichetta!r} senza URI")
                continue
            claim["group"] = gruppo
        claim["speech"] = speech
        claim["quote"] = " ".join(quote.split()) if "\n" in quote else quote
        claim["link"] = c.get("url") or ids.link_camera(speech) or SENATE_SITTINGS_URL
        claims.append(claim)

    giorno = (f["timestamp"] or "")[:10]
    risposta = {
        "schema": SCHEMA,
        "system": {"name": "Fascicoli", "url": "https://www.fascicoli.it"},
        "question": domande.get(f["id"][:8], DOMANDA_ASSENTE),
        "generated_at": f["timestamp"],
    }
    stats = json.loads(f["topic_stats"]) if f.get("topic_stats") else {}
    if stats.get("first_date") and stats.get("last_date"):
        risposta["period"] = {"from": stats["first_date"][:10], "to": stats["last_date"][:10]}
    scope = json.loads(f["scope"]) if f.get("scope") else None
    risposta["chambers"] = sorted({s["chamber"] for s in scope}) if scope else ["camera"]
    risposta["data_version"] = giorno
    risposta["claims"] = claims
    return risposta, problemi


def main() -> None:
    from neo4j import GraphDatabase

    p = argparse.ArgumentParser()
    p.add_argument("--uscita", default=str(Path(__file__).with_name("risposte")))
    p.add_argument("--fino-a", default="2026-08-06", help="ultima data coperta dai dati pubblicati")
    p.add_argument("--camere", default="camera", help="camere coperte dai dati pubblicati")
    p.add_argument("--quante", type=int, default=20, help="0 = tutte, senza filtro di copertura")
    a = p.parse_args()

    driver = GraphDatabase.driver(os.environ["NEO4J_URI"],
                                  auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]))
    fascicoli, persone, interventi, componenti = leggi(driver)
    driver.close()
    per_nome: dict = {}
    for r in persone:
        per_nome.setdefault(_piega(f"{r['first'] or ''} {r['last'] or ''}"), []).append(r["id"])
    camere = set(a.camere.split(","))
    domande = json.loads(DOMANDE.read_text(encoding="utf-8"))

    uscita = Path(a.uscita)
    uscita.mkdir(parents=True, exist_ok=True)
    scritte = 0
    for f in fascicoli:
        risposta, problemi = converti(f, per_nome, interventi, componenti, domande)
        if a.quante:
            dentro = risposta["claims"] and all(
                ("senato" if c["speech"].startswith("sen_") else "camera") in camere
                and (interventi.get(c["speech"]) or {}).get("date")
                and interventi[c["speech"]]["date"] <= a.fino_a
                for c in risposta["claims"])
            if not dentro:
                continue
            if f["id"][:8] not in domande:
                print(f"{f['id'][:8]}: manca la domanda in domande.json, salto", file=sys.stderr)
                continue
        for msg in problemi:
            print(f"{f['id'][:8]}: {msg}", file=sys.stderr)
        nome = uscita / f"fascicoli-{f['id'][:8]}.json"
        nome.write_text(json.dumps(risposta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        scritte += 1
        if a.quante and scritte >= a.quante:
            break
    print(f"{scritte} risposte in {uscita}")


if __name__ == "__main__":
    main()
