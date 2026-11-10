"""Carica le uscite trasformate in Postgres (schema/v3.sql): una seduta per transazione, l'anagrafica di un ramo
e di una legislatura in una transazione sola.

Libreria standard: psql riceve uno script con COPY. Una seduta cambiata si cancella e si ricarica nella stessa
transazione (ON DELETE CASCADE porta via punti, interventi, segmenti, reazioni): o c'è la versione nuova intera o resta
la vecchia intera.

Destinazione (`comando_psql`): senza PGHOST nell'ambiente (o in .env), il Postgres locale del contenitore `testi`;
con PGHOST, un Postgres remoto (Railway), con il psql del sistema o, se manca, quello dell'immagine pgvector/pgvector:pg16.
Le credenziali passano solo per variabili d'ambiente (PGHOST, PGPORT, PGUSER, PGPASSWORD, PGSSLMODE), mai negli argomenti.

Il caricamento ricorda file per file cosa ha caricato (`registro.py`): salta i file invariati, riprende dopo
un'interruzione, mette in quarantena i file che non passano i controlli o non si caricano e va avanti con gli altri.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from ..ambiente import QUI, env
from .registro import Registro

COLONNE = {
    "sitting": ["uri", "chamber", "body", "number", "date", "status", "source", "source_key", "source_hash", "kind", "record_url"],
    "agenda_item": ["uri", "sitting", "ord", "title"],
    "agenda_item_act": ["item", "act_ref"],
    "person": ["uri"],
    "speech": ["uri", "item", "ord", "person", "speaker_label", "as_group", "as_office", "anchor", "hash", "text", "markup"],
    "segment": ["uri", "speech", "ord", "start_char", "end_char", "kind", "hash"],
    "reaction": ["uri", "speech", "kind", "offset_char", "raw", "from_raw"],
    "reaction_from": ["reaction", "ord", "kind", "raw"],
}


IMMAGINE_PSQL = "pgvector/pgvector:pg16"            # la stessa del docker-compose.yml: psql 16
VARIABILI_PG = ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGSSLMODE")


def comando_psql() -> tuple[list[str], dict | None]:
    """Il comando psql (senza lo script) e l'ambiente in cui lanciarlo: None vuol dire l'ambiente di chi chiama."""
    opzioni = ["-d", "parliamentrag", "-v", "ON_ERROR_STOP=1", "-q"]
    if not env("PGHOST", ""):
        return ["docker", "compose", "exec", "-T", "testi", "psql", "-U", "parliamentrag", *opzioni], None
    ambiente = dict(os.environ)
    for v in VARIABILI_PG:                              # anche da .env: il processo le riceve per ambiente, non per argomento
        if env(v, ""):
            ambiente[v] = env(v)
    ambiente.setdefault("PGUSER", "parliamentrag")
    if shutil.which("psql"):
        return ["psql", *opzioni], ambiente
    # `-e NOME` senza valore: docker passa la variabile dal suo ambiente, senza scriverla negli argomenti
    return ["docker", "run", "--rm", "-i", *[x for v in VARIABILI_PG for x in ("-e", v)], IMMAGINE_PSQL, "psql", *opzioni], ambiente


def destinazione() -> str:
    """Nome della destinazione per il registro del caricamento: «locale» o host:porta del Postgres remoto."""
    host = env("PGHOST", "")
    return f"{host}:{env('PGPORT', '5432')}" if host else "locale"


def psql(script: str, timeout: int = 900) -> str:
    cmd, ambiente = comando_psql()
    r = subprocess.run(cmd, cwd=QUI, input=script, capture_output=True, text=True, timeout=timeout, env=ambiente)
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])
    return r.stdout


def leggi_csv(sql: str, timeout: int = 900) -> list[list[str]]:
    """Righe di una SELECT, via COPY in CSV. Legge in byte, perché subprocess in modo testo cambia gli a capo."""
    cmd, ambiente = comando_psql()
    r = subprocess.run([*cmd, "-c", f"COPY ({sql}) TO STDOUT WITH (FORMAT csv)"], cwd=QUI, capture_output=True, timeout=timeout, env=ambiente)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-800:])
    return list(csv.reader(io.StringIO(r.stdout.decode("utf-8"), newline="")))


def prova() -> None:
    """Il database risponde? Si fa all'inizio del giro: se no, il giro si ferma subito invece di fallire passo per passo."""
    try:
        psql("SELECT 1;\n", timeout=60)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
        raise RuntimeError(f"il database ({destinazione()}) non risponde: {str(e)[-300:]}") from e


def righe_tabelle(righe: list[dict]) -> dict[str, list[list]]:
    """Dai record dello schema v3 (nodi, archi, testi) alle righe delle tabelle."""
    nodi = {r["uri"]: r for r in righe if r["tipo"] == "nodo"}
    archi = [r for r in righe if r["tipo"] == "arco"]
    testi = {r["ref"]: r for r in righe if r["tipo"] == "testo"}
    padre = {}       # figlio -> padre per HAS_ITEM, HAS_SPEECH, HAS_SEGMENT, DURING
    chi, da, about, parti = {}, {}, [], []
    for a in archi:
        t = a["type"]
        if t in ("HAS_ITEM", "HAS_SPEECH", "HAS_SEGMENT"):
            padre[a["to"]] = a["from"]
        elif t == "DURING":
            padre[a["from"]] = a["to"]
        elif t == "BY":
            chi[a["from"]] = (a["to"], a.get("as_group"), a.get("as_office"))
        elif t == "FROM":
            da[a["from"]] = a["to_ref"]
            parti += [[a["from"], k, x["kind"], x["name"]] for k, x in enumerate(a.get("parts") or [], 1)]   # chi reagisce, una riga per parte
        elif t == "ABOUT":
            about.append([a["from"], a["to_ref"]])
    out = {k: [] for k in COLONNE}
    for u, n in nodi.items():
        l = n["label"]
        if l == "Sitting":
            out["sitting"].append([u, n["chamber"], n["body"], n["number"], n["date"], n["status"], n["source"], n.get("source_key"), n.get("source_hash"), n.get("kind"), n.get("record_url")])
        elif l == "AgendaItem":
            out["agenda_item"].append([u, padre[u], n["order"], n.get("title")])
        elif l == "Speech":
            p, g, o = chi.get(u, (None, n.get("declared_group"), None))
            t = testi[n["text_ref"]]
            out["speech"].append([u, padre[u], n["order"], p, n.get("speaker_label"), g, o, n.get("anchor"), n["hash"], t["text"], t.get("markup")])
            if p:
                out["person"].append([p])
        elif l == "Segment":
            out["segment"].append([u, padre[u], int(u.rsplit(":p", 1)[1]), n["start"], n["end"], n["kind"], n["hash"]])
        elif l == "Reaction":
            out["reaction"].append([u, padre[u], n["kind"], n["offset"], n["raw"], da.get(u)])
    out["reaction_from"] = parti
    out["agenda_item_act"] = [list(x) for x in {tuple(x) for x in about}]
    out["person"] = [list(x) for x in {tuple(x) for x in out["person"]}]
    return out


def _csv(righe: list[list]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows([["" if v is None else v for v in r] for r in righe])
    return buf.getvalue()


def script_seduta(righe: list[dict]) -> str:
    """Uno script psql: transazione, cancella la seduta, ricarica tutto con COPY (i dati CSV inline)."""
    t = righe_tabelle(righe)
    seduta = t["sitting"][0][0]
    parti = ["BEGIN;", f"DELETE FROM sitting WHERE uri = '{seduta.replace(chr(39), chr(39) * 2)}';"]
    for tabella in ("sitting", "agenda_item", "agenda_item_act"):
        if t[tabella]:
            parti.append(f"COPY {tabella} ({', '.join(COLONNE[tabella])}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(t[tabella])}\\.")
    if t["person"]:
        parti.append(f"CREATE TEMP TABLE p (uri text) ON COMMIT DROP;\nCOPY p FROM STDIN WITH (FORMAT csv);\n{_csv(t['person'])}\\.\n"
                     "INSERT INTO person (uri) SELECT uri FROM p ON CONFLICT DO NOTHING;")
    for tabella in ("speech", "segment", "reaction", "reaction_from"):
        if t[tabella]:
            parti.append(f"COPY {tabella} ({', '.join(COLONNE[tabella])}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(t[tabella])}\\.")
    parti.append(f"SELECT lega_argomenti({_lit(seduta)}, {int(seduta.split(':')[2])});")
    if t["reaction_from"]:
        parti.append(f"SELECT lega_reazioni({_lit(seduta + ':')});")
    if seduta.startswith("it:senato:"):                  # membri del governo che non sono senatori
        parti.append(f"SELECT lega_governo({_lit(seduta)});")
    parti.append("COMMIT;")
    return "\n".join(parti) + "\n"


ANAGRAFICA = {
    "person": ["uri", "camera_id", "senato_id", "given_name", "family_name", "sort_name", "gender", "birth_date", "birth_place", "photo",
               "education", "profession", "source", "source_uri"],
    "grp": ["uri", "chamber", "legislature", "kind", "name", "short_name", "start_date", "end_date", "part_of", "source", "source_uri", "aliases"],
    "body": ["uri", "chamber", "legislature", "kind", "kind_raw", "name", "start_date", "end_date", "part_of", "source", "source_uri"],
    "mandate": ["person", "chamber", "legislature", "start_date", "end_date", "end_reason", "validated", "constituency", "college", "system", "list", "source_uri", "kind"],
    "membership": ["person", "grp", "role", "start_date", "end_date", "end_reason"],
    "seat": ["person", "body", "role", "role_raw", "start_date", "end_date", "end_reason"],
    "office": ["person", "target", "title", "title_raw", "start_date", "end_date"],
    "grp_name": ["grp", "name", "short_name", "start_date", "end_date"],
}
# dal nome dell'arco alla tabella e alle colonne: from/to diventano le prime due colonne
ARCHI = {"MANDATE": "mandate", "MEMBER_OF": "membership", "SITS_ON": "seat", "OFFICE": "office", "NAMED": "grp_name"}
SENZA_DESTINAZIONE = ("mandate", "grp_name")       # archi con la sola chiave di partenza
_RINOMINA = {"start": "start_date", "end": "end_date"}


def _lit(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def righe_anagrafica(righe: list[dict]) -> dict[str, list[list]]:
    nodi = [r for r in righe if r["tipo"] == "nodo"]
    archi = [r for r in righe if r["tipo"] == "arco"]
    parte = {a["from"]: a["to"] for a in archi if a["type"] == "PART_OF"}
    out = {k: [] for k in ANAGRAFICA}
    for n in nodi:
        t = {"Person": "person", "Group": "grp", "Body": "body"}[n["label"]]
        x = {_RINOMINA.get(k, k): v for k, v in n.items()}
        if t == "grp":
            x["part_of"] = parte.get(n["uri"])
        out[t].append([_array(x.get(c)) if c == "aliases" else x.get(c) for c in ANAGRAFICA[t]])
    for a in archi:
        t = ARCHI.get(a["type"])
        if not t:
            continue
        x = {_RINOMINA.get(k, k): v for k, v in a.items()}
        x[ANAGRAFICA[t][0]] = a["from"]
        if t not in SENZA_DESTINAZIONE:
            x[ANAGRAFICA[t][1]] = a["to"]
        out[t].append([x.get(c) for c in ANAGRAFICA[t]])
    return out


def script_anagrafica(righe: list[dict]) -> str:
    """Una transazione: aggiorna le persone (non le cancella: gli interventi le citano), poi sostituisce gruppi, organi
    e relazioni di quel ramo e di quella legislatura. O c'è l'anagrafica nuova intera o resta la vecchia intera."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    ramo, leg = _lit(amb["chamber"]), int(amb["legislature"])
    t = righe_anagrafica(righe)
    colp = ANAGRAFICA["person"]
    parti = ["BEGIN;", "SET CONSTRAINTS ALL DEFERRED;",
             f"CREATE TEMP TABLE p (LIKE person INCLUDING DEFAULTS) ON COMMIT DROP;\nCOPY p ({', '.join(colp)}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(t['person'])}\\.",
             f"INSERT INTO person ({', '.join(colp)}, stub) SELECT {', '.join(colp)}, false FROM p ON CONFLICT (uri) DO UPDATE SET "
             + ", ".join(f"{c} = EXCLUDED.{c}" for c in colp[1:]) + ", stub = false;",
             f"DELETE FROM mandate WHERE chamber = {ramo} AND legislature = {leg};",
             f"DELETE FROM office WHERE target IN (SELECT uri FROM grp WHERE chamber = {ramo} AND legislature = {leg} UNION SELECT uri FROM body WHERE chamber = {ramo} AND legislature = {leg});",
             f"DELETE FROM grp WHERE chamber = {ramo} AND legislature = {leg};",
             f"DELETE FROM body WHERE chamber = {ramo} AND legislature = {leg};"]
    for tabella in ("grp", "body", "mandate", "membership", "seat", "office", "grp_name"):
        if t[tabella]:
            parti.append(f"COPY {tabella} ({', '.join(ANAGRAFICA[tabella])}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(t[tabella])}\\.")
    parti.append("COMMIT;")
    return "\n".join(parti) + "\n"


VOTI = {
    "vote": ["uri", "sitting", "chamber", "legislature", "number", "date", "title", "description", "kind", "kind_raw", "favor", "against",
             "abstain", "present", "voting", "majority", "approved", "secret", "final", "confidence", "ballots_match", "presided_by", "source", "source_uri",
             "source_url", "source_key", "source_hash"],
    "vote_act": ["vote", "act_ref"],
    "ballot": ["vote", "person", "result", "result_raw", "note", "grp"],
}


def script_voti(righe: list[dict]) -> str:
    """Le votazioni di una seduta in una transazione: si cancellano e si ricaricano intere, con i voti di ognuno."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    voti = [r for r in righe if r["tipo"] == "nodo" and r["label"] == "Vote"]
    archi = [r for r in righe if r["tipo"] == "arco"]
    t = {"vote": [[v.get(c) for c in VOTI["vote"]] for v in voti],
         "vote_act": sorted({(a["from"], a["to_ref"]) for a in archi if a["type"] == "ON"}),
         "ballot": [[a["to"], a["from"], a["result"], a.get("result_raw"), a.get("note"), a.get("group")] for a in archi if a["type"] == "VOTED"]}
    persone = sorted({a["from"] for a in archi if a["type"] == "VOTED"})
    parti = ["BEGIN;", f"DELETE FROM vote WHERE sitting = {_lit(amb['sitting'])} AND source = {_lit(amb.get('source', 'ocd'))};",
             f"CREATE TEMP TABLE p (uri text) ON COMMIT DROP;\nCOPY p FROM STDIN WITH (FORMAT csv);\n{_csv([[x] for x in persone])}\\.",
             "INSERT INTO person (uri) SELECT uri FROM p ON CONFLICT DO NOTHING;"]
    for tabella in ("vote", "vote_act", "ballot"):
        if t[tabella]:
            parti.append(f"COPY {tabella} ({', '.join(VOTI[tabella])}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(t[tabella])}\\.")
    leg = int(amb["legislature"])
    if amb.get("chamber", "camera") == "camera":
        parti.append(f"UPDATE vote_act v SET act = a.uri FROM act a JOIN vote x ON x.sitting = {_lit(amb['sitting'])} "
                     f"WHERE v.vote = x.uri AND a.chamber = 'camera' AND a.legislature = {leg} AND v.act_ref = 'ac{leg}_' || a.number;")
        # mozioni e risoluzioni (aic1_00346_19 -> it:camera:19:aic:1-00346): anche quando il mese degli atti non si ricarica
        parti.append(f"UPDATE vote_act v SET act = a.uri FROM act a JOIN vote x ON x.sitting = {_lit(amb['sitting'])} "
                     f"WHERE v.vote = x.uri AND v.act IS NULL AND v.act_ref ~ '^aic\\d_\\d+_{leg}$' "
                     f"AND a.uri = 'it:camera:{leg}:aic:' || replace(regexp_replace(v.act_ref, '^aic|_{leg}$', '', 'g'), '_', '-');")
    else:  # il Senato non dà il gruppo nel voto: lo si prende dall'anagrafica alla data della votazione
        parti.append(f"UPDATE ballot b SET grp = group_at(b.person, x.date) FROM vote x WHERE x.sitting = {_lit(amb['sitting'])} AND b.vote = x.uri;")
    parti.append("COMMIT;")
    return "\n".join(parti) + "\n"


ATTI = {
    "act": ["uri", "chamber", "legislature", "number", "kind", "kind_raw", "constitutional", "initiative", "title", "date", "description",
            "law_number", "law_date", "status", "status_date", "card_url", "text_urls", "source", "source_uri"],
    "act_step": ["uri", "act", "ord", "title", "date"],
    "act_version": ["uri", "act", "title", "date", "url"],
    "act_sponsor": ["act", "person", "first", "as_office"],
    "act_assignment": ["act", "body", "seat", "date", "title"],
    "act_rapporteur": ["act", "name_raw", "role", "raw", "person"],
    "act_joint": ["act", "main_act", "text_type"],
    "act_transmission": ["act", "other_ref", "date", "title", "provenance"],
}


def _array(v: list | None) -> str | None:
    return None if v is None else "{" + ",".join('"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"' for x in v) + "}"


def script_atti(righe: list[dict]) -> str:
    """Gli atti di un ramo e di una legislatura in una transazione: si sostituiscono interi. Poi si legano ai voti
    (vote_act) e i relatori alle persone, confrontando il nome con l'anagrafica."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    ramo, leg = _lit(amb["chamber"]), int(amb["legislature"])
    nodi = {r["uri"]: r for r in righe if r["tipo"] == "nodo"}
    archi = [r for r in righe if r["tipo"] == "arco"]
    padre = {a["to"]: a for a in archi if a["type"] in ("HAS_STEP", "HAS_VERSION")}
    t = {k: [] for k in ATTI}
    for u, n in nodi.items():
        if n["label"] == "Act":
            t["act"].append([n.get(c) if c != "text_urls" else _array(n.get("text_urls")) for c in ATTI["act"]])
        elif n["label"] == "Step":
            t["act_step"].append([u, padre[u]["from"], padre[u]["order"], n.get("title"), n.get("date")])
        elif n["label"] == "TextVersion":
            t["act_version"].append([u, padre[u]["from"], n.get("title"), n.get("date"), n.get("url")])
    for a in archi:
        if a["type"] == "SPONSORS":
            t["act_sponsor"].append([a["to"], a["from"], a["first"], a.get("as_office")])
        elif a["type"] == "ASSIGNED":
            t["act_assignment"].append([a["from"], a["to"], a.get("seat"), a.get("date"), a.get("title")])
        elif a["type"] == "RAPPORTEUR":
            t["act_rapporteur"].append([a["to"], a["from_ref"], a.get("role"), a.get("raw"), a.get("person")])
        elif a["type"] == "JOINED":
            t["act_joint"].append([a["from"], a["to"], a.get("text_type")])
        elif a["type"] == "TRANSMITTED":
            t["act_transmission"].append([a["from"], a.get("to_ref"), a.get("date"), a.get("title"), a.get("provenance")])
    # i relatori del Senato arrivano già con il senatore: la persona deve esserci prima della riga
    persone = sorted({r[1] for r in t["act_sponsor"]} | {r[4] for r in t["act_rapporteur"] if r[4]})
    parti = ["BEGIN;", f"DELETE FROM act WHERE chamber = {ramo} AND legislature = {leg} AND kind = 'bill';",
             f"CREATE TEMP TABLE p (uri text) ON COMMIT DROP;\nCOPY p FROM STDIN WITH (FORMAT csv);\n{_csv([[x] for x in persone])}\\.",
             "INSERT INTO person (uri) SELECT uri FROM p ON CONFLICT DO NOTHING;"]
    for tabella in ATTI:
        if t[tabella]:
            parti.append(f"COPY {tabella} ({', '.join(ATTI[tabella])}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(t[tabella])}\\.")
    parti += [
        # relatore: «SCHIFONE Marta» = cognome in maiuscolo e nome; si lega solo se c'è una persona sola con quel nome
        # (non gli stub: un membro del governo ha anche la scheda dell'id del Senato, con lo stesso nome)
        f"""UPDATE act_rapporteur r SET person = x.uri FROM (
              SELECT r2.ctid AS c, min(p.uri) AS uri FROM act_rapporteur r2 JOIN act a ON a.uri = r2.act
              JOIN person p ON upper(p.family_name || ' ' || p.given_name) = upper(r2.name_raw) AND NOT p.stub
              WHERE a.chamber = {ramo} AND a.legislature = {leg} GROUP BY r2.ctid HAVING count(*) = 1) x
            WHERE r.ctid = x.c;""",
        # poi cognome uguale e nome che comincia allo stesso modo («IEZZI Igor» = Iezzi Igor Giancarlo), sempre se unico
        f"""UPDATE act_rapporteur r SET person = x.uri FROM (
              SELECT r2.ctid AS c, min(p.uri) AS uri FROM act_rapporteur r2 JOIN act a ON a.uri = r2.act
              JOIN person p ON upper(p.family_name) = upper(substring(r2.name_raw from '^((?:[[:upper:]''’]+ ?)+) ')) AND NOT p.stub
               AND (upper(p.given_name) LIKE upper(regexp_replace(r2.name_raw, '^(?:[[:upper:]''’]+ ?)+ ', '')) || '%'
                    OR upper(regexp_replace(r2.name_raw, '^(?:[[:upper:]''’]+ ?)+ ', '')) LIKE upper(split_part(p.given_name, ' ', 1)) || '%')
              WHERE r2.person IS NULL AND a.chamber = {ramo} AND a.legislature = {leg} GROUP BY r2.ctid HAVING count(*) = 1) x
            WHERE r.ctid = x.c;""",
        # infine solo il cognome, se nella legislatura c'è un solo deputato con quel cognome («BICCHIELLI Pino»)
        f"""UPDATE act_rapporteur r SET person = x.uri FROM (
              SELECT r2.ctid AS c, min(p.uri) AS uri FROM act_rapporteur r2 JOIN act a ON a.uri = r2.act
              JOIN person p ON upper(p.family_name) = upper(substring(r2.name_raw from '^((?:[[:upper:]''’]+ ?)+) '))
              JOIN mandate m ON m.person = p.uri AND m.chamber = {ramo} AND m.legislature = {leg}
              WHERE r2.person IS NULL AND a.chamber = {ramo} AND a.legislature = {leg} GROUP BY r2.ctid HAVING count(DISTINCT p.uri) = 1) x
            WHERE r.ctid = x.c;""",
        # «ac19_N» è un atto della Camera: si lega solo ai voti della Camera, anche quando il caricamento è quello del Senato
        # (prima legava i voti della Camera al ddl del Senato con lo stesso numero)
        f"UPDATE vote_act v SET act = a.uri FROM act a, vote x WHERE x.uri = v.vote AND x.chamber = 'camera' "
        f"AND a.chamber = 'camera' AND a.legislature = {leg} AND v.act_ref = 'ac{leg}_' || a.number;",
        # Senato: il voto porta l'uri del ddl di dati.senato.it
        f"UPDATE vote_act v SET act = a.uri FROM act a, vote x WHERE x.uri = v.vote AND x.chamber = a.chamber "
        f"AND a.chamber = {ramo} AND a.legislature = {leg} AND v.act_ref = a.source_uri;",
        "COMMIT;"]
    return "\n".join(parti) + "\n"


ATTI_GOVERNO = {
    "act": ATTI["act"] + ["source_key"],
    "act_assignment": ["act", "body", "seat", "date", "title", "deadline", "basis", "opinion", "opinion_date"],
}


def script_atti_governo(righe: list[dict]) -> str:
    """Atti del Governo e nomine sottoposti a parere, di un ramo e di una legislatura: si sostituiscono interi, con le
    assegnazioni alle commissioni. Poi si legano agli argomenti dei sommari («Atto n. 439» = ag:439)."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    ramo, leg = _lit(amb["chamber"]), int(amb["legislature"])
    nodi = [r for r in righe if r["tipo"] == "nodo" and r["label"] == "Act"]
    if not nodi:
        return ""
    atti = [[_array(n.get("text_urls")) if c == "text_urls" else amb.get("source_key") if c == "source_key" else n.get(c)
             for c in ATTI_GOVERNO["act"]] for n in nodi]
    assegnazioni = [[a["from"], a["to"], a.get("seat"), a.get("date"), a.get("title"), a.get("deadline"), a.get("basis"),
                     a.get("opinion"), a.get("opinion_date")] for a in righe if a["tipo"] == "arco" and a["type"] == "ASSIGNED"]
    parti = ["BEGIN;", f"DELETE FROM act WHERE chamber = {ramo} AND legislature = {leg} AND kind IN ('government_act', 'appointment');",
             f"COPY act ({', '.join(ATTI_GOVERNO['act'])}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(atti)}\\."]
    if assegnazioni:
        parti.append(f"COPY act_assignment ({', '.join(ATTI_GOVERNO['act_assignment'])}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(assegnazioni)}\\.")
    parti += [f"UPDATE agenda_item_act x SET act = a.uri FROM act a, agenda_item i, sitting s WHERE x.act IS NULL AND x.act_ref ~ '^ag:' "
              f"AND i.uri = x.item AND s.uri = i.sitting AND s.chamber = {ramo} AND a.chamber = {ramo} AND a.legislature = {leg} "
              f"AND a.kind = 'government_act' AND a.number = split_part(x.act_ref, ':', 2);",
              # i fatti delle commissioni letti prima che l'atto ci fosse (pareri su «Atto n. 439»): si legano adesso
              f"UPDATE committee_fact f SET act = a.uri FROM act a WHERE f.act IS NULL AND f.chamber = {ramo} AND a.chamber = {ramo} "
              f"AND a.legislature = {leg} AND a.kind = 'government_act' AND cardinality(f.act_refs) = 1 AND f.act_refs[1] = 'ag:' || a.number;",
              "COMMIT;"]
    return "\n".join(parti) + "\n"


GOVERNO = {
    "government": ["uri", "name", "start_date", "end_date", "legislature", "source", "source_uri"],
    "ministry": ["uri", "government", "name", "portfolio", "source", "source_uri"],
    "office": ["person", "target", "title", "title_raw", "start_date", "end_date", "end_reason", "interim", "note", "source_uri"],
}


def script_governo(righe: list[dict]) -> str:
    """Governi della legislatura, ministeri e incarichi in una transazione. Le persone si aggiungono o si completano
    (solo i campi vuoti: per i deputati fa fede l'anagrafica della Camera), mai si cancellano."""
    nodi = [r for r in righe if r["tipo"] == "nodo"]
    archi = [r for r in righe if r["tipo"] == "arco" and r["type"] == "OFFICE"]
    rin = lambda d: {_RINOMINA.get(k, k): v for k, v in d.items()}
    t = {"government": [[rin(n).get(c) for c in GOVERNO["government"]] for n in nodi if n["label"] == "Government"],
         "ministry": [[rin(n).get(c) for c in GOVERNO["ministry"]] for n in nodi if n["label"] == "Ministry"],
         "office": [[a["from"], a["to"]] + [rin(a).get(c) for c in GOVERNO["office"][2:]] for a in archi]}
    persone = [[rin(n).get(c) for c in ANAGRAFICA["person"]] for n in nodi if n["label"] == "Person"]
    governi = ", ".join(_lit(r[0]) for r in t["government"]) or "''"
    colp = ANAGRAFICA["person"]
    parti = ["BEGIN;",
             f"CREATE TEMP TABLE p (LIKE person INCLUDING DEFAULTS) ON COMMIT DROP;\nCOPY p ({', '.join(colp)}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(persone)}\\.",
             f"INSERT INTO person ({', '.join(colp)}, stub) SELECT {', '.join(colp)}, false FROM p ON CONFLICT (uri) DO UPDATE SET "
             + ", ".join(f"{c} = coalesce(person.{c}, EXCLUDED.{c})" for c in colp[1:]) + ", stub = false;",
             f"DELETE FROM office WHERE target IN ({governi}) OR target IN (SELECT uri FROM ministry WHERE government IN ({governi}));",
             f"DELETE FROM government WHERE uri IN ({governi});"]
    for tabella in GOVERNO:
        if t[tabella]:
            parti.append(f"COPY {tabella} ({', '.join(GOVERNO[tabella])}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(t[tabella])}\\.")
    parti.append("COMMIT;")
    return "\n".join(parti) + "\n"


BOLLETTINO = {
    "sitting": ["uri", "chamber", "body", "number", "date", "status", "source", "source_key", "source_hash", "kind", "body_code", "body_name",
                "seat", "bulletin_number", "provisional", "presidency", "presided_by", "government_present", "start_time", "end_time"],
    "agenda_item": ["uri", "sitting", "ord", "title", "stage", "procedural"],
    "agenda_item_act": ["item", "act_ref"],
    "speech": ["uri", "item", "ord", "person", "speaker_label", "as_group", "as_office", "kind", "anchor", "hash", "text"],
    "document": ["uri", "kind", "date", "body_code", "title", "anchor", "acts", "hash", "text", "source", "source_key"],
    "speech_mention": ["speech", "ord", "person", "surface", "method"],
}


def script_commissione(righe: list[dict]) -> str:
    """Un documento di commissione in una transazione: il comunicato del Bollettino di un giorno (sommario e allegati)
    o uno stenografico (verbatim). Si sostituisce tutto ciò che viene dallo stesso documento della fonte.
    L'organo si lega all'anagrafica: commissioni permanenti per numero, le altre per nome; le riunite restano col codice.
    Chi parla senza link alla scheda si lega al deputato in carica quel giorno con lo stesso nome, se è uno solo."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    nodi = [r for r in righe if r["tipo"] == "nodo"]
    archi = [r for r in righe if r["tipo"] == "arco"]
    testi = {r["ref"]: r for r in righe if r["tipo"] == "testo"}
    padre = {a["to"]: a["from"] for a in archi if a["type"] in ("HAS_ITEM", "HAS_SPEECH")}
    chi = {a["from"]: a["to"] for a in archi if a["type"] == "BY"}
    leg, codice, giorno = int(amb["legislature"]), amb["body_code"], amb["date"]
    ramo = amb.get("chamber", "camera")
    provvisorio = f"it:{ramo}:{leg}:comm:{codice}"
    t = {k: [] for k in BOLLETTINO}
    for n in nodi:
        if n["label"] == "Sitting":
            x = {**n, "body": provvisorio}
            t["sitting"].append([x.get(c) for c in BOLLETTINO["sitting"]])
        elif n["label"] == "AgendaItem":
            t["agenda_item"].append([n["uri"], padre[n["uri"]], n["order"], n.get("title"), n.get("stage"), bool(n.get("service"))])
            t["agenda_item_act"] += [[n["uri"], ref] for ref in n.get("acts", [])]
        elif n["label"] == "Speech":
            t["speech"].append([n["uri"], padre[n["uri"]], n["order"], chi.get(n["uri"]), n.get("speaker_label"), n.get("declared_group"),
                                n.get("as_office"), n["kind"], n.get("anchor"), n["hash"], testi[n["text_ref"]]["text"]])
        elif n["label"] == "Document":
            t["document"].append([n["uri"], n["kind"], n["date"], n["body_code"], n.get("title"), n.get("anchor"), _array(n.get("acts")),
                                  n["hash"], testi[n["text_ref"]]["text"], n["source"], amb.get("source_key")])
    t["speech_mention"] = [[a["from"], a["order"], a["to"], a.get("surface"), a["method"]] for a in archi if a["type"] == "MENTIONS"]
    persone = sorted({r[3] for r in t["speech"] if r[3]} | {r[2] for r in t["speech_mention"]} | {r[BOLLETTINO["sitting"].index("presided_by")] for r in t["sitting"] if r[BOLLETTINO["sitting"].index("presided_by")]})
    filtro = f"source = {_lit(amb['source'])} AND source_key = {_lit(amb['source_key'])}"
    # la stessa seduta può arrivare da due documenti della fonte: la Camera a volte pubblica la bozza e la versione
    # definitiva sotto numeri diversi (stenografico 0001 in bozza, 0003 definitivo, stessa seduta). La definitiva prende
    # il posto di qualunque altra versione; una bozza non tocca una definitiva già caricata, e si salta
    uris = ", ".join(_lit(r[0]) for r in t["sitting"]) or "NULL"
    bozza = any(n.get("provisional") for n in nodi if n["label"] == "Sitting")
    altre = f"uri IN ({uris}) AND NOT ({filtro})"
    parti = ["BEGIN;", f"DELETE FROM sitting WHERE {filtro};", f"DELETE FROM document WHERE {filtro};",
             f"DELETE FROM sitting WHERE {altre}{' AND provisional' if bozza else ''};",
             f"CREATE TEMP TABLE p (uri text) ON COMMIT DROP;\nCOPY p FROM STDIN WITH (FORMAT csv);\n{_csv([[x] for x in persone])}\\.",
             "INSERT INTO person (uri) SELECT uri FROM p ON CONFLICT DO NOTHING;"]
    for tabella in BOLLETTINO:
        if t[tabella]:
            parti.append(f"COPY {tabella} ({', '.join(BOLLETTINO[tabella])}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(t[tabella])}\\.")
    numerica = ramo == "camera" and codice.isdigit() and len(codice) == 2 and 1 <= int(codice) <= 14
    # Senato: il nome del sommario («7ª Commissione permanente») è l'inizio del nome in anagrafica, che aggiunge la materia
    # (con le cifre: norm_nome le toglie e «1ª» e «10ª Commissione» diventerebbero uguali)
    confronto = ("lower(regexp_replace(b.name, '[^0-9A-Za-z]', '', 'g')) LIKE lower(regexp_replace(s.body_name, '[^0-9A-Za-z]', '', 'g')) || '%'"
                 if ramo == "senato" else "norm_nome(b.name) = norm_nome(s.body_name)")
    risolto = (f"'it:camera:{leg}:body:o{leg}_35' || {_lit(codice)}" if numerica else
               f"(SELECT min(b.uri) FROM body b WHERE b.chamber = {_lit(ramo)} AND b.legislature = {leg} AND {confronto} "
               f"HAVING count(*) = 1)")
    parti += [f"UPDATE sitting s SET body = coalesce({risolto}, s.body) WHERE s.{filtro.replace('AND ', 'AND s.')};",
              f"UPDATE document d SET body = (SELECT s.body FROM sitting s WHERE s.{filtro.replace('AND ', 'AND s.')} LIMIT 1) WHERE d.{filtro.replace('AND ', 'AND d.')};",
              f"""UPDATE speech sp SET person = x.uri FROM (
                    SELECT sp2.uri AS u, min(p.uri) AS uri FROM speech sp2 JOIN agenda_item i ON i.uri = sp2.item JOIN sitting s ON s.uri = i.sitting
                    JOIN person p ON upper(p.given_name || ' ' || p.family_name) = upper(sp2.speaker_label)
                    JOIN mandate m ON m.person = p.uri AND m.chamber = {_lit(ramo)} AND m.start_date <= s.date AND (m.end_date IS NULL OR m.end_date >= s.date)
                    WHERE sp2.person IS NULL AND s.{filtro.replace('AND ', 'AND s.')} GROUP BY sp2.uri HAVING count(DISTINCT p.uri) = 1) x
                  WHERE sp.uri = x.u;""",
              f"SELECT lega_argomenti(s.uri, {leg}) FROM sitting s WHERE s.{filtro.replace('AND ', 'AND s.')};",
              "COMMIT;"]
    if bozza and "superata" in psql(f"SELECT 'superata' FROM sitting WHERE {altre} AND NOT coalesce(provisional, false) LIMIT 1;"):
        return ""                                     # bozza superata: c'è già la versione definitiva
    return "\n".join(parti) + "\n"


AIC = {
    "act": ["uri", "chamber", "legislature", "number", "kind", "kind_raw", "title", "text", "date", "closed_date", "concluded",
            "card_url", "source", "source_uri", "source_key"],
    "act_sponsor": ["act", "person", "first"],
    "act_addressee": ["act", "ministry"],
    "act_subject": ["act", "concept"],
}


def script_aic(righe: list[dict]) -> str:
    """Gli atti di sindacato ispettivo presentati in un mese, in una transazione; poi si legano ai voti
    (gli ordini del giorno votati) e agli argomenti del Bollettino (le interrogazioni svolte in commissione)."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    leg, k = int(amb["legislature"]), amb["source_key"]
    nodi = [r for r in righe if r["tipo"] == "nodo"]
    archi = [r for r in righe if r["tipo"] == "arco"]
    t = {"act": [[{**n, "source_key": k}.get(c) for c in AIC["act"]] for n in nodi],
         "act_sponsor": [[a["to"], a["from"], a["first"]] for a in archi if a["type"] == "SPONSORS"],
         "act_addressee": [[a["from"], a["to"]] for a in archi if a["type"] == "ADDRESSED_TO"],
         "act_subject": [[a["from"], a["to"]] for a in archi if a["type"] == "SUBJECT"]}
    persone = sorted({r[1] for r in t["act_sponsor"]})
    ramo = amb.get("chamber", "camera")
    parti = ["BEGIN;", f"DELETE FROM act WHERE source_key = {_lit(k)} AND chamber = {_lit(ramo)};",
             f"CREATE TEMP TABLE p (uri text) ON COMMIT DROP;\nCOPY p FROM STDIN WITH (FORMAT csv);\n{_csv([[x] for x in persone])}\\.",
             "INSERT INTO person (uri) SELECT uri FROM p ON CONFLICT DO NOTHING;"]
    for tabella in AIC:
        if t[tabella]:
            parti.append(f"COPY {tabella} ({', '.join(AIC[tabella])}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(t[tabella])}\\.")
    parti += [
        # voti: aic9_00080_004_19 -> it:camera:19:aic:9-00080-004
        f"""UPDATE vote_act v SET act = a.uri FROM act a WHERE a.source_key = {_lit(k)} AND v.act IS NULL
              AND v.act_ref LIKE 'aic%' AND a.uri = 'it:{ramo}:{leg}:aic:' || replace(regexp_replace(v.act_ref, '^aic|_{leg}$', '', 'g'), '_', '-');""",
        # ordini del giorno: il voto non porta il suffisso del testo esaminato («9/00115-A/002» -> aic9_00115_002_19);
        # si lega se, con la stessa data fra presentazione e voto, il candidato è uno solo
        f"""UPDATE vote_act v SET act = x.uri FROM (
              SELECT v2.vote, v2.act_ref, min(a.uri) AS uri FROM vote_act v2 JOIN vote vo ON vo.uri = v2.vote
              JOIN act a ON a.source_key = {_lit(k)} AND a.date = vo.date
               AND regexp_replace(a.number, '^(\\d)/(\\d+)(-[A-Z]+)?/(\\d+)$', 'aic\\1_\\2_\\4_{leg}') = v2.act_ref
              WHERE v2.act IS NULL AND v2.act_ref LIKE 'aic%' GROUP BY v2.vote, v2.act_ref HAVING count(*) = 1) x
            WHERE v.vote = x.vote AND v.act_ref = x.act_ref;""",
        # Bollettino: «aic:5-04321»
        f"""UPDATE agenda_item_act x SET act = a.uri FROM act a WHERE a.source_key = {_lit(k)} AND x.act IS NULL
              AND x.act_ref LIKE 'aic:%' AND a.uri = 'it:{ramo}:{leg}:' || x.act_ref;""",
        "COMMIT;"]
    return "\n".join(parti) + "\n"


def script_video(righe: list[dict]) -> str:
    """Il video di una seduta con i tratti degli interventi, in una transazione."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    v = next(r for r in righe if r["tipo"] == "nodo" and r["label"] == "Video")
    tratti = [[a["to"], a["order"], a.get("from"), a.get("anchor"), a.get("label"), a.get("start"), a.get("end"), a.get("clock"),
               a.get("webtv_id")]
              for a in righe if a["tipo"] == "arco" and a["type"] == "HAS_VIDEO"]
    col_v = ["uri", "event_id", "sitting", "kind", "title", "url", "start_ts", "end_ts", "source", "source_key"]
    parti = ["BEGIN;", f"DELETE FROM video WHERE uri = {_lit(v['uri'])};",
             f"COPY video ({', '.join(col_v)}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv([[{**v, 'source_key': amb['source_key']}.get(c) for c in col_v]])}\\."]
    if tratti:
        parti.append(f"COPY video_segment (video, ord, speech, anchor, label, start_s, end_s, clock, webtv_id) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(tratti)}\\.")
    parti.append("COMMIT;")
    return "\n".join(parti) + "\n"


def script_odg(righe: list[dict]) -> str:
    """Una seduta prevista con i suoi argomenti. Se la seduta si è già tenuta (c'è il resoconto) non si tocca:
    il resoconto vince sempre sull'ordine del giorno."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    nodi = [r for r in righe if r["tipo"] == "nodo"]
    s = next(n for n in nodi if n["label"] == "Sitting")
    voci = [n for n in nodi if n["label"] == "AgendaItem"]
    col_s = ["uri", "chamber", "body", "number", "date", "status", "kind", "start_time", "source", "source_key", "source_hash"]
    col_i = ["uri", "sitting", "ord", "title", "text", "scheduled_time", "rapporteurs"]
    u, leg = _lit(s["uri"]), int(amb["legislature"])
    prevista = f"EXISTS (SELECT 1 FROM sitting WHERE uri = {u} AND status = 'planned')"
    parti = ["BEGIN;", f"DELETE FROM sitting WHERE uri = {u} AND status = 'planned';",
             f"CREATE TEMP TABLE s_ (LIKE sitting INCLUDING DEFAULTS) ON COMMIT DROP;",
             f"COPY s_ ({', '.join(col_s)}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv([[s.get(c) for c in col_s]])}\\.",
             f"INSERT INTO sitting ({', '.join(col_s)}) SELECT {', '.join(col_s)} FROM s_ WHERE NOT EXISTS (SELECT 1 FROM sitting WHERE uri = {u});",
             "CREATE TEMP TABLE i_ (uri text, sitting text, ord int, title text, text text, scheduled_time text, rapporteurs text) ON COMMIT DROP;",
             f"COPY i_ ({', '.join(col_i)}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv([[v['uri'], s['uri'], v['order'], v.get('title'), v.get('text'), v.get('scheduled_time'), v.get('rapporteurs')] for v in voci])}\\.",
             f"INSERT INTO agenda_item ({', '.join(col_i)}) SELECT {', '.join(col_i)} FROM i_ WHERE {prevista};",
             "CREATE TEMP TABLE a_ (item text, act_ref text) ON COMMIT DROP;",
             f"COPY a_ FROM STDIN WITH (FORMAT csv);\n{_csv(sorted({(v['uri'], a) for v in voci for a in v['acts']}))}\\.",
             f"INSERT INTO agenda_item_act (item, act_ref) SELECT item, act_ref FROM a_ WHERE {prevista};",
             f"SELECT lega_argomenti({u}, {leg});",
             "COMMIT;"]
    return "\n".join(parti) + "\n"


def script_calendario(righe: list[dict]) -> str:
    """Il calendario dei lavori di un ramo: sostituisce per intero quello di prima (le voci cambiano a ogni aggiornamento)."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    voci = [r for r in righe if r["tipo"] == "nodo" and r["label"] == "CalendarItem"]
    if not voci:
        return ""
    col = ["uri", "chamber", "date", "ord", "when_text", "title", "acts", "calendar", "updated", "source", "source_key"]
    dati = [[v["uri"], v["chamber"], v["date"], v["order"], v.get("when"), v["title"],
             "{" + ",".join('"' + a.replace('"', "") + '"' for a in v.get("acts") or []) + "}", v.get("calendar"), v.get("updated"),
             amb["source"], amb.get("source_key")] for v in voci]
    return "\n".join(["BEGIN;", f"DELETE FROM calendar_item WHERE chamber = {_lit(amb['chamber'])} AND source = {_lit(amb['source'])};",
                      f"COPY calendar_item ({', '.join(col)}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(dati)}\\.", "COMMIT;"]) + "\n"


CONVOCAZIONI = ["uri", "chamber", "body", "body_name", "date", "ord", "start_time", "when_text", "seat", "place", "number", "text", "acts",
                "cancelled", "published", "url", "source", "source_key"]


def script_convocazioni(righe: list[dict]) -> str:
    """Le convocazioni di una commissione (un giorno alla Camera, una settimana al Senato): sostituiscono quelle della
    stessa pagina; quelle delle pagine passate restano. Una pagina senza convocazioni toglie quelle di prima."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    voci = [r for r in righe if r["tipo"] == "nodo" and r["label"] == "Convocation"]
    dati = [[v["uri"], v["chamber"], v.get("body"), v["body_name"], v["date"], v["order"], v.get("start_time"), v.get("when"), v.get("seat"),
             v.get("place"), v.get("number"), v.get("text"), _array(v.get("acts") or []), bool(v.get("cancelled")), v.get("published"),
             v.get("url"), amb["source"], amb["source_key"]] for v in voci]
    parti = ["BEGIN;", f"DELETE FROM convocation WHERE source_key = {_lit(amb['source_key'])};"]
    if dati:
        parti += [f"DELETE FROM convocation WHERE uri = ANY (ARRAY[{', '.join(_lit(d[0]) for d in dati)}]);",
                  f"COPY convocation ({', '.join(CONVOCAZIONI)}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(dati)}\\."]
    return "\n".join(parti + ["COMMIT;"]) + "\n"


DOC_META = ["uri", "kind", "date", "body_code", "body", "title", "author_raw", "hearing", "sitting_date", "acts", "url", "format",
            "third_party", "hash", "source", "source_key"]


def script_documenti(righe: list[dict]) -> str:
    """Metadati dagli elenchi (aggiornano, non toccano il testo) o testo da un file (aggiorna solo il testo)."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    nodi = [r for r in righe if r["tipo"] == "nodo"]
    if amb["kind"] == "documenti_elenco":
        dati = [[_array(n["acts"]) if c == "acts" else (amb["source_key"] if c == "source_key" else
                 hashlib.sha256(n["url"].encode()).hexdigest()[:16] if c == "hash" else n.get(c)) for c in DOC_META] for n in nodi]
        agg = ", ".join(f"{c} = EXCLUDED.{c}" for c in DOC_META[1:] if c != "hash")
        return "\n".join(["BEGIN;", f"CREATE TEMP TABLE d_ (LIKE document INCLUDING DEFAULTS) ON COMMIT DROP;",
                           f"COPY d_ ({', '.join(DOC_META)}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(dati)}\\.",
                           f"INSERT INTO document ({', '.join(DOC_META)}) SELECT {', '.join(DOC_META)} FROM d_ ON CONFLICT (uri) DO UPDATE SET {agg};",
                           "COMMIT;"]) + "\n"
    testi = {r["ref"]: r["text"] for r in righe if r["tipo"] == "testo"}
    n = nodi[0]
    t = testi.get(n.get("text_ref") or "")
    riga = [[n["uri"], "document", n["hash"], t, n.get("format"), "camera_documenti", amb["source_key"]]]
    return "\n".join(["BEGIN;", "CREATE TEMP TABLE t_ (uri text, kind text, hash text, text text, format text, source text, source_key text) ON COMMIT DROP;",
                       f"COPY t_ FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(riga)}\\.",
                       "INSERT INTO document (uri, kind, hash, text, format, source, source_key) SELECT * FROM t_ "
                       "ON CONFLICT (uri) DO UPDATE SET text = EXCLUDED.text, hash = EXCLUDED.hash;", "COMMIT;"]) + "\n"


DOC_INTERO = ["uri", "kind", "date", "title", "hearing", "author_raw", "code", "acts", "url", "format", "third_party", "hash", "text",
              "source", "source_key"]


def script_documento(righe: list[dict]) -> str:
    """Un documento intero (metadati e testo), sostituito: per i dossier."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    n = next(r for r in righe if r["tipo"] == "nodo")
    testo = next((r["text"] for r in righe if r["tipo"] == "testo"), None)
    riga = [[_array(n.get("acts")) if c == "acts" else testo if c == "text" else amb["source_key"] if c == "source_key" else n.get(c)
             for c in DOC_INTERO]]
    return "\n".join(["BEGIN;", f"DELETE FROM document WHERE uri = {_lit(n['uri'])};",
                       f"COPY document ({', '.join(DOC_INTERO)}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(riga)}\\.", "COMMIT;"]) + "\n"


EMENDAMENTI = ["uri", "act", "number", "kind", "action", "article", "venue", "committee", "sitting_number", "sitting_date", "group_title",
               "status", "outcome", "decree", "identical", "hash", "text", "source_key", "presented"]


def script_emendamenti(righe: list[dict]) -> str:
    """Tutti gli emendamenti di un progetto di legge in una transazione: si sostituiscono interi."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    testi = {r["ref"]: r["text"] for r in righe if r["tipo"] == "testo"}
    nodi = [r for r in righe if r["tipo"] == "nodo"]
    firme = [r for r in righe if r["tipo"] == "arco" and r["type"] == "SIGNS"]
    dati = [[_array(n.get("identical")) if c == "identical" else testi.get(n.get("text_ref") or "") if c == "text"
             else amb["source_key"] if c == "source_key" else n.get(c) for c in EMENDAMENTI] for n in nodi]
    f = [[a["to"], a["order"], a.get("from"), a.get("first"), a.get("family_raw"), a.get("given_raw"), a.get("kind_raw")] for a in firme]
    persone = sorted({a["from"] for a in firme if a.get("from")})
    parti = ["BEGIN;", f"DELETE FROM amendment WHERE source_key = {_lit(amb['source_key'])};",
             f"CREATE TEMP TABLE p (uri text) ON COMMIT DROP;\nCOPY p FROM STDIN WITH (FORMAT csv);\n{_csv([[x] for x in persone])}\\.",
             "INSERT INTO person (uri) SELECT uri FROM p ON CONFLICT DO NOTHING;"]
    if dati:
        parti.append(f"COPY amendment ({', '.join(EMENDAMENTI)}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(dati)}\\.")
    if f:
        parti.append(f"COPY amendment_signer (amendment, ord, person, first, family_raw, given_raw, kind_raw) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(f)}\\.")
    parti.append("COMMIT;")
    return "\n".join(parti) + "\n"


def script_testo_atto(righe: list[dict]) -> str:
    """Il testo di una versione di un progetto di legge, con articoli e norme citate, in una transazione."""
    amb = next(r for r in righe if r["tipo"] == "ambito")
    n = next(r for r in righe if r["tipo"] == "nodo")
    testo = next(r["text"] for r in righe if r["tipo"] == "testo")
    c = amb["code"]
    art = [[c, i, a.get("number"), a.get("anchor"), a.get("text")] for i, a in enumerate(n["articles"], 1)]
    cit = [[c, x["urn"], x.get("label")] for x in n["citations"]]
    parti = ["BEGIN;", f"DELETE FROM act_text WHERE code = {_lit(c)};",
             f"COPY act_text (code, hash, text, source_key, act, kind) FROM STDIN WITH (FORMAT csv, NULL '');\n"
             f"{_csv([[c, n['hash'], testo, amb['source_key'], n.get('act'), n.get('kind')]])}\\."]
    if art:
        parti.append(f"COPY act_article (code, ord, number, anchor, text) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(art)}\\.")
    if cit:
        parti.append(f"COPY act_citation (code, urn, label) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(cit)}\\.")
    parti.append("COMMIT;")
    return "\n".join(parti) + "\n"


def script_corrispondenze(righe: list[dict]) -> str:
    """Le corrispondenze fra id della stessa persona, sostituite intere; le persone della Camera che sono senatori
    si completano (solo i campi vuoti)."""
    nodi = [r for r in righe if r["tipo"] == "nodo"]
    archi = [[a["from"], a["to"], a["method"]] for a in righe if a["tipo"] == "arco" and a["type"] == "SAME_AS"]
    colp = ["uri", "camera_id", "given_name", "family_name", "sort_name", "gender", "source", "source_uri"]
    parti = ["BEGIN;", "CREATE TEMP TABLE p (LIKE person INCLUDING DEFAULTS) ON COMMIT DROP;",
             f"COPY p ({', '.join(colp)}) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv([[n.get(c) for c in colp] for n in nodi])}\\.",
             f"INSERT INTO person ({', '.join(colp)}, stub) SELECT {', '.join(colp)}, false FROM p ON CONFLICT (uri) DO UPDATE SET "
             + ", ".join(f"{c} = coalesce(person.{c}, EXCLUDED.{c})" for c in colp[1:]) + ", stub = false;",
             "DELETE FROM person_same_as WHERE person LIKE 'it:person:camera:%' AND same_as LIKE 'it:person:senato:%';"]
    if archi:
        parti.append(f"COPY person_same_as (person, same_as, method) FROM STDIN WITH (FORMAT csv);\n{_csv(archi)}\\.")
    parti.append("COMMIT;")
    return "\n".join(parti) + "\n"


def script_concetti(righe: list[dict]) -> str:
    """Un thesaurus intero: si sostituisce in una transazione."""
    ambito = next(r for r in righe if r["tipo"] == "ambito")
    nodi = [[n["uri"], n["scheme"], n["label_it"], n.get("label_en"), _array(n.get("broader") or []), n["source"]]
            for n in righe if n["tipo"] == "nodo"]
    return "\n".join(["BEGIN;", f"DELETE FROM concept WHERE scheme = {_lit(ambito['scheme'])};",
                      f"COPY concept (uri, scheme, label_it, label_en, broader, source) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(nodi)}\\.",
                      "COMMIT;"]) + "\n"


def script_allineamenti(cartella) -> str:
    """Concetti TESEO e collegamenti fra thesauri da dati/allineamenti/: file piccoli e curati, si sostituiscono interi."""
    teseo = [json.loads(x) for x in (cartella / "teseo-concetti.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    righe = [json.loads(x) for x in (cartella / "teseo-eurovoc.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    concetti = [[c["uri"], "teseo", c["label_it"], None, None, "dati.senato.it"] for c in teseo]
    legami = [[r["teseo"], r["eurovoc"], r["relation"], r.get("confidence"), r.get("score"), r["method"], r.get("verified"),
               r.get("verified_by"), r.get("verified_at")] for r in righe]
    return "\n".join(["BEGIN;", "DELETE FROM concept WHERE scheme = 'teseo';",
                      f"COPY concept (uri, scheme, label_it, label_en, broader, source) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(concetti)}\\.",
                      "DELETE FROM concept_match;",
                      f"COPY concept_match (from_concept, to_concept, relation, confidence, score, method, verified, verified_by, verified_at) FROM STDIN WITH (FORMAT csv, NULL '');\n{_csv(legami)}\\.",
                      "COMMIT;"]) + "\n"


def script_gruppi_voti(ramo: str, leg: int) -> str:
    """Dopo un'anagrafica nuova, il gruppo nei voti già caricati di quel ramo: le componenti del Misto (o un'adesione
    corretta) valgono anche per i voti di prima. Al Senato il gruppo viene sempre dall'anagrafica alla data del voto
    (come in script_voti); alla Camera lo attribuisce la fonte, e si completa solo dove manca o è il Misto senza componente."""
    filtro = ("" if ramo == "senato" else
              f" AND (b2.grp IS NULL OR b2.grp IN (SELECT part_of FROM grp WHERE kind = 'misto_component' AND chamber = 'camera' AND legislature = {leg}))")
    return (f"UPDATE ballot b SET grp = x.g FROM (SELECT b2.vote, b2.person, group_at(b2.person, v.date) AS g FROM ballot b2 "
            f"JOIN vote v ON v.uri = b2.vote WHERE v.chamber = {_lit(ramo)} AND v.legislature = {leg}{filtro}) x\n"
            f"WHERE b.vote = x.vote AND b.person = x.person AND x.g IS NOT NULL AND b.grp IS DISTINCT FROM x.g;\n")


# tipo di uscita (kind dell'ambito) -> funzione che fa lo script e voce del riepilogo; senza ambito, una seduta
SCRIPT = {"anagrafica": (script_anagrafica, "anagrafiche_e_atti"), "voti": (script_voti, "voti"),
          "commissione": (script_commissione, "sedute"), "testo_atto": (script_testo_atto, "sedute"),
          "emendamenti": (script_emendamenti, "sedute"), "dossier": (script_documento, "sedute"),
          "documenti_elenco": (script_documenti, "sedute"), "documento_testo": (script_documenti, "sedute"),
          "odg": (script_odg, "sedute"), "calendario": (script_calendario, "sedute"), "video": (script_video, "sedute"), "aic": (script_aic, "anagrafiche_e_atti"),
          "corrispondenze": (script_corrispondenze, "anagrafiche_e_atti"), "governo": (script_governo, "anagrafiche_e_atti"),
          "concetti": (script_concetti, "anagrafiche_e_atti"), "atti": (script_atti, "anagrafiche_e_atti"),
          "atti_governo": (script_atti_governo, "anagrafiche_e_atti"), "convocazioni": (script_convocazioni, "sedute")}


def leggi_uscita(f: Path) -> list[dict]:
    return [json.loads(x) for x in f.read_text(encoding="utf-8").split("\n") if x.strip()]  # non splitlines(): spezza anche su U+2028, che nei testi c'è


def carica_righe(righe: list[dict]) -> str:
    """Carica un file di uscita; restituisce la voce del riepilogo, o «vuoti» se non c'era niente da caricare."""
    amb = righe[0] if righe and righe[0]["tipo"] == "ambito" else {}
    funzione, voce = SCRIPT.get(amb.get("kind"), (script_seduta, "sedute"))
    if amb.get("kind") == "testo_atto" and not any(r["tipo"] == "testo" for r in righe):
        return "vuoti"                                 # versione annunciata, testo non ancora pubblicato alla fonte
    script = funzione(righe)
    if not script:
        return "vuoti"                                 # bozza superata: c'è già la versione definitiva
    psql(script)
    if amb.get("kind") == "anagrafica":
        psql(script_gruppi_voti(amb["chamber"], int(amb["legislature"])), timeout=3600)
    return voce


def ordine(f: Path) -> tuple:
    """Prima l'anagrafica (gli interventi e i voti citano le persone), poi governo e corrispondenze, poi gli atti
    (i voti si legano agli atti), poi il resto."""
    return (0 if f.name.endswith("-anagrafica.jsonl") else 1 if f.name.endswith(("-governo.jsonl", "-corrispondenze.jsonl"))
            else 2 if f.name.endswith(("-atti.jsonl", "-atti-governo.jsonl")) or "-aic-" in f.name else 3, str(f))


def applica_schema(registro: Registro) -> str:
    """schema/v3.sql solo se è cambiato dall'ultima volta che è entrato in questa destinazione. Con lock_timeout:
    se una tabella è occupata (un indice in costruzione, una query lunga) lo schema aspetta il giro dopo invece di
    fermare il database."""
    testo = (QUI / "schema" / "v3.sql").read_text()
    h = hashlib.sha256(testo.encode()).hexdigest()
    if registro.leggi("schema") == h:
        return "invariato"
    psql("SET lock_timeout = '5s';\n" + testo)
    registro.scrivi("schema", h)
    return "applicato"


def _legami() -> None:
    # dopo voti e atti: gli id dei gruppi nei voti, gli ordini del giorno votati e le votazioni su emendamenti e articoli
    # (schema/v3.sql); poi le reazioni
    # ancora senza chi reagisce, se sono arrivati gruppi o persone nuovi
    psql("SELECT lega_gruppi_voti();\nSELECT lega_odg_voti(l), lega_voti_seguito(l) FROM (SELECT DISTINCT legislature AS l FROM vote WHERE chamber = 'camera') x;\n"
         "SELECT lega_voti_titolo_senato(l) FROM (SELECT DISTINCT legislature AS l FROM vote WHERE chamber = 'senato') y;", timeout=3600)
    psql("SELECT lega_reazioni('it:');", timeout=3600)


def carica(ctx) -> dict:
    """Carica i file delle uscite non ancora in questa destinazione, uno per transazione, nell'ordine di `ordine`.
    Un file che non passa i controlli o non si carica va in quarantena e gli altri vanno avanti. Il caricamento ha un suo
    tempo (`[carica] tempo_minuti`): finito quello si ferma fra un file e l'altro e il giro dopo riprende da lì."""
    from ..controlli.uscite import errori_file
    cfg = ctx.config.get("carica", {})
    tempo = float(cfg.get("tempo_minuti", 150)) * 60
    registro = Registro(ctx.cartella, destinazione())
    avvisi = []
    try:
        schema = applica_schema(registro)
    except Exception as e:                              # si carica con lo schema di prima; i file che ne hanno bisogno vanno in quarantena
        schema = "non applicato"
        avvisi.append(f"schema/v3.sql non applicato, si riprova al giro dopo: {str(e)[-300:]}")
    cartella = ctx.cartella / "uscite" / "v3"
    inizio, conti, quarantena, di_fila = time.time(), {}, [], 0
    file_ = sorted(cartella.rglob("*.jsonl"), key=ordine)
    rimandati = 0
    for n, f in enumerate(file_):
        if time.time() - inizio > tempo:
            rimandati = len(file_) - n                  # file non ancora guardati: il giro dopo riprende da qui
            break
        h = registro.da_caricare(f)
        if h is None:
            continue
        q = registro.quarantena_di(f)
        if q and q["impronta"] == h and q["fase"] == "controllo":
            quarantena.append(f"{f.name}: {q['motivo'][:200]}")      # lo ricontrolla controlla_uscite, a ogni giro
            continue
        try:
            righe = leggi_uscita(f)
            errori = errori_file(righe)
        except Exception as e:
            righe, errori = [], [f"file illeggibile: {e}"]
        if errori:
            registro.in_quarantena(f, h, "controllo", "; ".join(errori), ctx.giro)
            quarantena.append(f"{f.name}: {'; '.join(errori)[:200]}")
            continue
        try:
            voce = carica_righe(righe)
        except Exception as e:                          # la seduta resta com'era, intera; le altre vanno avanti
            registro.in_quarantena(f, h, "caricamento", str(e)[-1000:], ctx.giro)
            quarantena.append(f"{f.name}: {str(e)[-200:]}")
            di_fila += 1
            if di_fila % 5 == 0:
                prova()                                 # cinque errori di fila: se il database non risponde, inutile andare avanti
            continue
        di_fila = 0
        registro.caricato(f, h)
        conti[voce] = conti.get(voce, 0) + 1
        if voce in ("voti", "anagrafiche_e_atti") or (righe and righe[0].get("kind") == "emendamenti"):   # i fascicoli legano le votazioni
            registro.scrivi("legami", "da fare")        # si ricorda anche se il passo si interrompe prima dei legami
    if registro.leggi("legami"):
        _legami()
        registro.scrivi("legami", "")
    allineamenti = ctx.cartella / "allineamenti"
    if (allineamenti / "teseo-eurovoc.jsonl").exists():
        psql(script_allineamenti(allineamenti))
    if quarantena:
        avvisi.append(f"{len(quarantena)} file in quarantena, si riprovano al giro dopo: " + "; ".join(quarantena[:3]))
    if rimandati:
        avvisi.append(f"tempo del caricamento finito: {rimandati} file da guardare al giro dopo")
    return {**{f"{k}_caricati": v for k, v in conti.items()}, "schema": schema, "in_quarantena": len(quarantena),
            "esempi_quarantena": quarantena[:10], "rimandati": rimandati, **({"avviso": avvisi} if avvisi else {})}
