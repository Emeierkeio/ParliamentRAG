"""Export aperto dei dati: tabelle Parquet per Hugging Face ogni notte, RDF per Zenodo come bozza una volta al mese.

    python -m pipeline esporta [--hf] [--zenodo] [--senza-caricare]

--hf      scrive le tabelle in dati/esporta/hf e le carica su Hugging Face (emeierkeio/parliamentrag-leg19, HF_TOKEN)
--zenodo  scrive il grafo RDF in dati/esporta/rdf e apre una nuova versione del record Zenodo (concept DOI
          10.5281/zenodo.21560331, ZENODO_TOKEN) come bozza: la pubblica Mirko dal browser, perché un DOI pubblicato
          resta per sempre
--senza-caricare  scrive i file e si ferma (per guardarli prima)

Si esporta solo ciò che viene dagli open data, con la licenza delle fonti (CC BY-SA 4.0 per la Camera, che obbliga anche
i derivati; CC BY 3.0 per il Senato). Restano fuori i vettori, le conversazioni della chat, i riassunti scritti dall'AI
e il registro delle visite. Il database si legge con psql in CSV (`carica.postgres.comando_psql`), una tabella alla
volta su disco, così la memoria non cresce con le righe.
"""

from __future__ import annotations

import csv
import datetime as dt
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from ..ambiente import QUI, env
from ..carica.postgres import comando_psql

QUI_MODULO = Path(__file__).resolve().parent
REPO_HF = "emeierkeio/parliamentrag-leg19"
CONCEPT_ZENODO = "21560331"
LEG = 19
RAMI = "('camera', 'senato')"

# ---------- tabelle: nome -> (SELECT, tipi delle colonne non testuali) ----------
# i tipi: i int32, I int64, d data, b booleano; il resto è testo. Gli array diventano testo JSON.

_SED = f"SELECT uri FROM sitting WHERE chamber IN {RAMI}"
TABELLE: dict[str, tuple[str, dict[str, str]]] = {
    "persons": ("""
        SELECT p.uri AS id, p.given_name, p.family_name, p.sort_name, p.gender, p.birth_date, p.birth_place, p.education,
               p.profession, p.qid AS wikidata, p.camera_id, p.senato_id, p.source_uri,
               (SELECT string_agg(s.same_as, ' ' ORDER BY s.same_as) FROM person_same_as s WHERE s.person = p.uri) AS same_as
        FROM person p WHERE NOT p.stub ORDER BY p.uri""", {"birth_date": "d"}),
    "mandates": (f"""
        SELECT person, chamber, legislature, kind, start_date, end_date, end_reason, constituency, college, system, list
        FROM mandate WHERE legislature = {LEG} ORDER BY person, start_date""",
                 {"legislature": "i", "start_date": "d", "end_date": "d"}),
    "organizations": (f"""
        SELECT uri AS id, chamber, legislature, kind, name, short_name, start_date, end_date, part_of, source_uri
        FROM grp WHERE legislature = {LEG}
        UNION ALL
        SELECT uri, chamber, legislature, kind, name, NULL, start_date, end_date, part_of, source_uri
        FROM body WHERE legislature = {LEG} ORDER BY 1""", {"legislature": "i", "start_date": "d", "end_date": "d"}),
    "memberships": (f"""
        SELECT m.person, m.grp AS organization, 'group' AS type, m.role, NULL AS role_raw, m.start_date, m.end_date, m.end_reason
        FROM membership m JOIN grp g ON g.uri = m.grp WHERE g.legislature = {LEG}
        UNION ALL
        SELECT s.person, s.body, 'body', s.role, s.role_raw, s.start_date, s.end_date, s.end_reason
        FROM seat s JOIN body b ON b.uri = s.body WHERE b.legislature = {LEG} ORDER BY 1, 6""",
                    {"start_date": "d", "end_date": "d"}),
    "sessions": (f"""
        SELECT uri AS id, chamber, body, body_name, kind, number, date, status, start_time, end_time, presided_by, record_url
        FROM sitting WHERE chamber IN {RAMI} ORDER BY date, uri""", {"number": "i", "date": "d"}),
    "debates": (f"""
        SELECT a.uri AS id, a.sitting AS session, a.ord, a.title, a.stage, a.procedural, a.rapporteurs
        FROM agenda_item a WHERE a.sitting IN ({_SED}) ORDER BY a.sitting, a.ord""", {"ord": "i", "procedural": "b"}),
    "speeches": (f"""
        SELECT sp.uri AS id, s.chamber, s.date, s.uri AS session, sp.item AS debate, sp.ord, sp.person, sp.speaker_label,
               sp.as_group, sp.as_office, sp.kind, sp.text
        FROM speech sp JOIN agenda_item a ON a.uri = sp.item JOIN sitting s ON s.uri = a.sitting
        WHERE s.chamber IN {RAMI} ORDER BY s.date, sp.item, sp.ord""", {"date": "d", "ord": "i"}),
    "votes": (f"""
        SELECT v.uri AS id, v.chamber, v.sitting AS session, v.number, v.date, v.title, v.description, v.kind, v.favor,
               v.against, v.abstain, v.present, v.voting, v.majority, v.approved, v.secret, v.final, v.confidence,
               (SELECT string_agg(DISTINCT va.act, ' ') FROM vote_act va WHERE va.vote = v.uri AND va.act IS NOT NULL) AS acts,
               v.source_uri, v.source_url
        FROM vote v WHERE v.legislature = {LEG} ORDER BY v.date, v.uri""",
              {"number": "i", "date": "d", "favor": "i", "against": "i", "abstain": "i", "present": "i", "voting": "i",
               "majority": "i", "approved": "b", "secret": "b", "final": "b", "confidence": "b"}),
    "individual_votes": (f"""
        SELECT b.vote, b.person, b.result, b.grp AS "group"
        FROM ballot b JOIN vote v ON v.uri = b.vote WHERE v.legislature = {LEG} ORDER BY b.vote, b.person""", {}),
    "acts": (f"""
        SELECT uri AS id, chamber, number, kind, kind_raw, constitutional, initiative, title, date, description, status,
               status_date, concluded, law_number, law_date, card_url, array_to_json(text_urls)::text AS text_urls, source_uri
        FROM act WHERE legislature = {LEG} ORDER BY uri""",
             {"constitutional": "b", "date": "d", "status_date": "d", "concluded": "b", "law_date": "d"}),
    "act_sponsors": (f"""
        SELECT s.act, s.person, s.first, s.as_office FROM act_sponsor s JOIN act a ON a.uri = s.act
        WHERE a.legislature = {LEG} ORDER BY 1, 3 DESC, 2""", {"first": "b"}),
    "act_joints": (f"""
        SELECT j.act, j.main_act, j.text_type FROM act_joint j JOIN act a ON a.uri = j.act WHERE a.legislature = {LEG}
        ORDER BY 2, 1""", {}),
    "act_subjects": (f"""
        SELECT s.act, s.concept, c.label_it, c.label_en FROM act_subject s JOIN act a ON a.uri = s.act
        LEFT JOIN concept c ON c.uri = s.concept WHERE a.legislature = {LEG} ORDER BY 1, 2""", {}),
    "amendments": (f"""
        SELECT e.uri AS id, e.act, e.number, e.kind, e.action, e.article, e.venue, e.committee, e.sitting_number,
               e.sitting_date, e.presented, e.group_title, e.status, e.outcome, e.decree, e.text,
               (SELECT string_agg(s.person, ' ' ORDER BY s.ord) FROM amendment_signer s WHERE s.amendment = e.uri) AS signers
        FROM amendment e JOIN act a ON a.uri = e.act WHERE a.legislature = {LEG} ORDER BY e.act, e.uri""",
                   {"sitting_number": "i", "sitting_date": "d", "presented": "d"}),
    "amendment_deadlines": (f"""
        SELECT d.uri AS id, d.chamber, d.act, array_to_string(d.act_refs, ' ') AS act_refs, d.body, d.body_name, d.sitting,
               d.sitting_date, d.kind, d.event, d.due_date, to_char(d.due_time, 'HH24:MI') AS due_time, d.presented, d.sentence
        FROM amendment_deadline d WHERE d.uri LIKE '%:{LEG}:termine:%' ORDER BY d.due_date, d.uri""",
                            {"sitting_date": "d", "due_date": "d", "presented": "i"}),
}


def _csv(sql: str, file: Path) -> None:
    """La SELECT in un file CSV con l'intestazione, scritto da psql mentre legge (niente righe in memoria)."""
    cmd, ambiente = comando_psql()
    una_riga = " ".join(sql.split())
    with file.open("wb") as f:
        r = subprocess.run([*cmd, "-c", f"COPY ({una_riga}) TO STDOUT WITH (FORMAT csv, HEADER)"], cwd=QUI, stdout=f,
                           stderr=subprocess.PIPE, timeout=3 * 3600, env=ambiente)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-800:])


def _righe(file: Path):
    csv.field_size_limit(1 << 30)                   # alcuni interventi e testi di emendamenti superano i 128 kB
    with file.open(encoding="utf-8", newline="") as f:
        lettore = csv.reader(f)
        intest = next(lettore)
        for r in lettore:
            yield dict(zip(intest, r))


# ---------- Hugging Face ----------

def tabelle_hf(cartella: Path) -> dict:
    """Ogni tabella in Parquet (zstd), letta dal CSV a blocchi. Torna il conteggio delle righe per la scheda."""
    import pyarrow as pa
    import pyarrow.csv as pcsv
    import pyarrow.parquet as pq

    tipi = {"i": pa.int32(), "I": pa.int64(), "d": pa.date32(), "b": pa.bool_()}
    cartella.mkdir(parents=True, exist_ok=True)
    righe = {}
    for nome, (sql, colonne) in TABELLE.items():
        grezzo = cartella / f"{nome}.csv"
        _csv(sql, grezzo)
        with grezzo.open(encoding="utf-8") as f:
            intest = next(csv.reader(f))
        conv = pcsv.ConvertOptions(column_types={c: tipi.get(colonne.get(c), pa.string()) for c in intest},
                                   true_values=["t"], false_values=["f"], strings_can_be_null=True)
        lettura = pcsv.ReadOptions(block_size=64 << 20)
        n = 0
        with pcsv.open_csv(grezzo, read_options=lettura, convert_options=conv,
                           parse_options=pcsv.ParseOptions(newlines_in_values=True)) as flusso:
            with pq.ParquetWriter(cartella / f"{nome}.parquet", flusso.schema, compression="zstd") as w:
                for blocco in flusso:
                    w.write_batch(blocco)
                    n += blocco.num_rows
        grezzo.unlink()
        righe[nome] = n
        print(f"{nome}: {n} righe", flush=True)
    return righe


def ultime_date() -> dict[str, str]:
    """La data dell'ultima seduta tenuta, per ramo: la scheda dice fin dove arrivano i dati."""
    f = QUI / "dati" / "esporta" / ".date.csv"
    f.parent.mkdir(parents=True, exist_ok=True)
    _csv(f"SELECT chamber, max(date) AS al FROM sitting WHERE chamber IN {RAMI} AND status = 'held' GROUP BY 1 ORDER BY 1", f)
    out = {r["chamber"]: r["al"] for r in _righe(f)}
    f.unlink()
    return out


def scheda_hf(cartella: Path, righe: dict, date: dict) -> None:
    testo = (QUI_MODULO / "scheda_hf.md").read_text(encoding="utf-8")
    valori = {"GENERATED": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
              "DATI_CAMERA": date.get("camera", ""), "DATI_SENATO": date.get("senato", ""),
              **{f"N_{k.upper()}": f"{v:,}" for k, v in righe.items()}}
    for k, v in valori.items():
        testo = testo.replace("{{" + k + "}}", v)
    (cartella / "README.md").write_text(testo, encoding="utf-8")
    (cartella / "export_meta.json").write_text(json.dumps(
        {"row_counts": righe, "data_as_of": date, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
         "source": "https://github.com/Emeierkeio/ParliamentRAG/tree/main/pipeline/esporta"}, indent=2), encoding="utf-8")


def carica_hf(cartella: Path) -> str:
    from huggingface_hub import HfApi

    token = env("HF_TOKEN", "")
    if not token:
        raise RuntimeError("manca HF_TOKEN (.env)")
    c = HfApi(token=token).upload_folder(
        folder_path=str(cartella), repo_id=REPO_HF, repo_type="dataset", allow_patterns=["*.parquet", "README.md", "export_meta.json"],
        delete_patterns=["*.parquet"], commit_message=f"Dati al {dt.date.today().isoformat()}")
    return str(getattr(c, "commit_url", c))


# ---------- RDF ----------

BASE = "https://w3id.org/parliamentrag/"
PR = BASE + "ontology#"
PREFISSI = {
    "pr": PR, "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#", "owl": "http://www.w3.org/2002/07/owl#", "foaf": "http://xmlns.com/foaf/0.1/",
    "org": "http://www.w3.org/ns/org#", "skos": "http://www.w3.org/2004/02/skos/core#", "dcterms": "http://purl.org/dc/terms/",
    "schema": "https://schema.org/", "ocd": "http://dati.camera.it/ocd/", "osr": "http://dati.senato.it/osr/",
}

# i termini pr: che il dump usa, dichiarati nel dump stesso: nome -> (classe o proprietà, commento, padre)
ONTOLOGIA = {
    "Mandate": ("class", "The term of office of a member in one house and legislature.", None),
    "Session": ("class", "A sitting of the floor or of a committee, in the Chamber or the Senate.", None),
    "Debate": ("class", "An agenda item of a sitting.", None),
    "Speech": ("class", "A speech in the record of a sitting, with its full text.", None),
    "Vote": ("class", "A roll-call vote.", None),
    "IndividualVote": ("class", "The vote cast by one member in one roll-call vote.", None),
    "Amendment": ("class", "An amendment to the text of an act, in committee or on the floor.", "osr:Emendamento"),
    "AmendmentDeadline": ("class", "A deadline for tabling amendments to an act in committee, read from the committee summary record.", None),
    "chamber": ("data", "camera (Chamber of Deputies) or senato (Senate).", None),
    "kind": ("data", "The kind of resource as classified by the source or by the loader.", None),
    "number": ("data", "Number of the sitting, the vote, the act or the amendment.", None),
    "order": ("data", "Position within the parent resource.", None),
    "text": ("data", "Full text of the speech or of the amendment.", None),
    "speakerLabel": ("data", "The speaker as written in the record (e.g. PRESIDENTE).", None),
    "asGroup": ("data", "The group the record attributes to the speaker or the voter at that date.", None),
    "status": ("data", "Last step of the act's process, or status of the sitting or the amendment.", None),
    "outcome": ("data", "Outcome of the amendment or of the individual vote (favor, against, abstain, absent, mission, ...).", None),
    "inFavor": ("data", "Votes in favour.", None), "against": ("data", "Votes against.", None),
    "abstained": ("data", "Abstentions.", None), "present": ("data", "Members present.", None),
    "voting": ("data", "Members voting.", None), "majority": ("data", "Majority required.", None),
    "approved": ("data", "The vote passed.", None), "secret": ("data", "Secret ballot.", None),
    "finalVote": ("data", "Final vote on the act.", None), "confidenceVote": ("data", "Vote of confidence.", None),
    "lawNumber": ("data", "Number of the law the act became.", None), "lawDate": ("data", "Date of that law.", None),
    "initiative": ("data", "Who presented the act (Parlamentare, Governo, Regioni, ...).", None),
    "role": ("data", "Role in the organization, as given by the source.", None),
    "constituency": ("data", "Electoral constituency of the mandate.", None),
    "session": ("object", "The sitting the debate or the vote belongs to.", None),
    "debate": ("object", "The agenda item the speech belongs to.", None),
    "spokenBy": ("object", "The member who delivered the speech.", None),
    "member": ("object", "The person holding the mandate.", None),
    "body": ("object", "The organ (floor or committee) of the sitting.", None),
    "onAct": ("object", "An act the roll-call vote is on.", None),
    "primarySignatoryOf": ("object", "The member is the first signatory of the act or amendment.", None),
    "coSignatoryOf": ("object", "The member co-signed the act or amendment.", None),
    "jointWith": ("object", "The main act this act is examined jointly with (abbinato).", None),
    "amends": ("object", "The act whose text the amendment changes.", None),
    "hasDeadline": ("object", "A deadline for tabling amendments to the act.", None),
    "setIn": ("object", "The sitting whose summary record reports the deadline.", None),
    "dueDate": ("data", "Day the deadline expires.", None), "dueTime": ("data", "Time the deadline expires, when stated.", None),
    "event": ("data", "What the record says of the deadline: fixed, extended (moved to a new date) or expired.", None),
    "evidence": ("data", "The sentence of the summary record the fact is read from (written by the clerks, not by a member).", None),
    "voter": ("object", "The member who cast the individual vote.", None),
    "onVote": ("object", "The roll-call vote the individual vote belongs to.", None),
}


def iri(uri: str) -> str:
    """L'IRI pubblico di una risorsa del v3: it:camera:19:sed0739 -> https://w3id.org/parliamentrag/it/camera/19/sed0739."""
    if uri.startswith("http"):
        return f"<{quote(uri, safe=':/#?&=%~.-_')}>"
    return f"<{BASE}{quote(uri.replace(':', '/'), safe='/.-_~')}>"


def lett(v: str, tipo: str | None = None, lingua: str | None = None) -> str:
    s = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    return f'"{s}"' + (f"^^xsd:{tipo}" if tipo else f"@{lingua}" if lingua else "")


class Grafo:
    """Turtle a una tripla per riga (prefissi in testa), compresso con gzip mentre si scrive."""

    def __init__(self, file: Path, prefissi: bool = True):
        self.f = gzip.open(file, "wt", encoding="utf-8", compresslevel=6)
        self.n = 0
        self.prefissi = prefissi
        if prefissi:
            self.f.write("".join(f"@prefix {k}: <{v}> .\n" for k, v in PREFISSI.items()) + "\n")

    def t(self, s: str, p: str, o: str | None) -> None:
        if o is None or o in ('""', ""):
            return
        if not self.prefissi:                       # N-Triples: niente prefissi, IRI interi
            p = _intero(p)
            o = o if o.startswith(("<", '"')) else _intero(o)
            o = o.replace("^^xsd:", f"^^<{PREFISSI['xsd']}") + ">" if "^^xsd:" in o else o
        self.f.write(f"{s} {p} {o} .\n")
        self.n += 1

    def chiudi(self) -> int:
        self.f.close()
        return self.n


def _intero(nome: str) -> str:
    pre, _, locale = nome.partition(":")
    return f"<{PREFISSI[pre]}{locale}>"


def _v(r: dict, k: str, tipo: str | None = None) -> str | None:
    v = r.get(k)
    if not v:
        return None
    if tipo == "boolean":
        v = "true" if v == "t" else "false"
    return lett(v, tipo)


def grafo_rdf(cartella: Path) -> dict:
    """parliamentrag_kg.ttl.gz (tutto tranne i voti dei singoli) e parliamentrag_votes.nt.gz (i voti dei singoli)."""
    cartella.mkdir(parents=True, exist_ok=True)
    g = Grafo(cartella / "parliamentrag_kg.ttl.gz")
    for nome, (genere, commento, padre) in ONTOLOGIA.items():
        s = f"pr:{nome}"
        g.t(s, "rdf:type", {"class": "owl:Class", "object": "owl:ObjectProperty", "data": "owl:DatatypeProperty"}[genere])
        g.t(s, "rdfs:comment", lett(commento, lingua="en"))
        if padre:
            g.t(s, "rdfs:subClassOf", padre)

    def tabella(nome: str):
        f = cartella / f".{nome}.csv"
        _csv(TABELLE[nome][0], f)
        try:
            yield from _righe(f)
        finally:
            f.unlink(missing_ok=True)

    for r in tabella("persons"):
        s = iri(r["id"])
        g.t(s, "rdf:type", "foaf:Person")
        g.t(s, "foaf:givenName", _v(r, "given_name"))
        g.t(s, "foaf:familyName", _v(r, "family_name"))
        g.t(s, "foaf:name", lett(f"{r['given_name']} {r['family_name']}".strip()) if r["family_name"] else None)
        g.t(s, "schema:birthDate", _v(r, "birth_date", "date"))
        g.t(s, "schema:birthPlace", _v(r, "birth_place"))
        g.t(s, "foaf:gender", _v(r, "gender"))
        g.t(s, "schema:hasOccupation", _v(r, "profession"))
        g.t(s, "owl:sameAs", iri(r["source_uri"]) if r["source_uri"] else None)
        g.t(s, "owl:sameAs", f"<http://www.wikidata.org/entity/{r['wikidata']}>" if r["wikidata"] else None)
        for altro in (r["same_as"] or "").split():
            g.t(s, "owl:sameAs", iri(altro))
    for r in tabella("mandates"):
        s = iri(f"mandate:{r['person']}:{r['chamber']}:{r['legislature']}:{r['start_date']}")
        g.t(s, "rdf:type", "pr:Mandate")
        g.t(s, "pr:member", iri(r["person"]))
        g.t(s, "pr:chamber", _v(r, "chamber"))
        g.t(s, "schema:startDate", _v(r, "start_date", "date"))
        g.t(s, "schema:endDate", _v(r, "end_date", "date"))
        g.t(s, "pr:constituency", _v(r, "constituency"))
    for r in tabella("organizations"):
        s = iri(r["id"])
        g.t(s, "rdf:type", "org:Organization")
        g.t(s, "rdfs:label", lett(r["name"], lingua="it"))
        g.t(s, "skos:altLabel", lett(r["short_name"], lingua="it") if r["short_name"] else None)
        g.t(s, "pr:chamber", _v(r, "chamber"))
        g.t(s, "pr:kind", _v(r, "kind"))
        g.t(s, "schema:startDate", _v(r, "start_date", "date"))
        g.t(s, "schema:endDate", _v(r, "end_date", "date"))
        g.t(s, "org:subOrganizationOf", iri(r["part_of"]) if r["part_of"] else None)
        g.t(s, "owl:sameAs", iri(r["source_uri"]) if r["source_uri"] else None)
    for r in tabella("memberships"):
        chiave = hashlib.sha1("|".join(r[k] for k in ("person", "organization", "role", "start_date")).encode()).hexdigest()[:16]
        s = iri(f"membership:{chiave}")
        g.t(s, "rdf:type", "org:Membership")
        g.t(s, "org:member", iri(r["person"]))
        g.t(s, "org:organization", iri(r["organization"]))
        g.t(s, "pr:role", _v(r, "role_raw") or _v(r, "role"))
        g.t(s, "schema:startDate", _v(r, "start_date", "date"))
        g.t(s, "schema:endDate", _v(r, "end_date", "date"))
    for r in tabella("sessions"):
        s = iri(r["id"])
        g.t(s, "rdf:type", "pr:Session")
        g.t(s, "pr:chamber", _v(r, "chamber"))
        g.t(s, "pr:body", iri(r["body"]) if r["body"] else None)
        g.t(s, "pr:number", _v(r, "number", "integer"))
        g.t(s, "dcterms:date", _v(r, "date", "date"))
        g.t(s, "pr:status", _v(r, "status"))
        g.t(s, "foaf:page", iri(r["record_url"]) if r["record_url"] else None)
    for r in tabella("debates"):
        s = iri(r["id"])
        g.t(s, "rdf:type", "pr:Debate")
        g.t(s, "pr:session", iri(r["session"]))
        g.t(s, "pr:order", _v(r, "ord", "integer"))
        g.t(s, "dcterms:title", lett(r["title"], lingua="it") if r["title"] else None)
    for r in tabella("speeches"):
        s = iri(r["id"])
        g.t(s, "rdf:type", "pr:Speech")
        g.t(s, "pr:debate", iri(r["debate"]))
        g.t(s, "pr:order", _v(r, "ord", "integer"))
        g.t(s, "pr:spokenBy", iri(r["person"]) if r["person"] else None)
        g.t(s, "pr:speakerLabel", _v(r, "speaker_label"))
        g.t(s, "pr:asGroup", _v(r, "as_group"))
        g.t(s, "pr:text", lett(r["text"], lingua="it") if r["text"] else None)
    for r in tabella("acts"):
        s = iri(r["id"])
        g.t(s, "rdf:type", "ocd:atto")
        g.t(s, "pr:chamber", _v(r, "chamber"))
        g.t(s, "pr:number", _v(r, "number"))
        g.t(s, "pr:kind", _v(r, "kind"))
        g.t(s, "pr:initiative", _v(r, "initiative"))
        g.t(s, "dcterms:title", lett(r["title"], lingua="it") if r["title"] else None)
        g.t(s, "dcterms:date", _v(r, "date", "date"))
        g.t(s, "pr:status", _v(r, "status"))
        g.t(s, "pr:lawNumber", _v(r, "law_number"))
        g.t(s, "pr:lawDate", _v(r, "law_date", "date"))
        g.t(s, "foaf:page", iri(r["card_url"]) if r["card_url"] else None)
        g.t(s, "owl:sameAs", iri(r["source_uri"]) if r["source_uri"] else None)
    for r in tabella("act_sponsors"):
        g.t(iri(r["person"]), "pr:primarySignatoryOf" if r["first"] == "t" else "pr:coSignatoryOf", iri(r["act"]))
    for r in tabella("act_joints"):
        g.t(iri(r["act"]), "pr:jointWith", iri(r["main_act"]))
    concetti = {}
    for r in tabella("act_subjects"):
        g.t(iri(r["act"]), "dcterms:subject", iri(r["concept"]))
        concetti.setdefault(r["concept"], (r["label_it"], r["label_en"]))
    for c, (it, en) in concetti.items():
        g.t(iri(c), "rdf:type", "skos:Concept")
        g.t(iri(c), "skos:prefLabel", lett(it, lingua="it") if it else None)
        g.t(iri(c), "skos:prefLabel", lett(en, lingua="en") if en else None)
    for r in tabella("votes"):
        s = iri(r["id"])
        g.t(s, "rdf:type", "pr:Vote")
        g.t(s, "pr:session", iri(r["session"]))
        g.t(s, "pr:chamber", _v(r, "chamber"))
        g.t(s, "pr:number", _v(r, "number", "integer"))
        g.t(s, "dcterms:date", _v(r, "date", "date"))
        g.t(s, "dcterms:title", lett(r["title"], lingua="it") if r["title"] else None)
        g.t(s, "dcterms:description", lett(r["description"], lingua="it") if r["description"] else None)
        g.t(s, "pr:kind", _v(r, "kind"))
        for k, p in (("favor", "inFavor"), ("against", "against"), ("abstain", "abstained"), ("present", "present"),
                     ("voting", "voting"), ("majority", "majority")):
            g.t(s, f"pr:{p}", _v(r, k, "integer"))
        for k, p in (("approved", "approved"), ("secret", "secret"), ("final", "finalVote"), ("confidence", "confidenceVote")):
            g.t(s, f"pr:{p}", _v(r, k, "boolean"))
        for a in (r["acts"] or "").split():
            g.t(s, "pr:onAct", iri(a))
        g.t(s, "foaf:page", iri(r["source_url"]) if r["source_url"] else None)
        g.t(s, "owl:sameAs", iri(r["source_uri"]) if r["source_uri"] else None)
    emendamenti = 0
    for r in tabella("amendments"):
        s = iri(r["id"])
        emendamenti += 1
        g.t(s, "rdf:type", "pr:Amendment")
        g.t(s, "pr:amends", iri(r["act"]))
        g.t(s, "pr:number", _v(r, "number"))
        g.t(s, "pr:kind", _v(r, "kind"))
        g.t(s, "dcterms:date", _v(r, "presented", "date"))
        g.t(s, "pr:status", _v(r, "status"))
        g.t(s, "pr:outcome", _v(r, "outcome"))
        g.t(s, "pr:text", lett(r["text"], lingua="it") if r["text"] else None)
        for i, p in enumerate((r["signers"] or "").split()):
            g.t(iri(p), "pr:primarySignatoryOf" if i == 0 else "pr:coSignatoryOf", s)
    for r in tabella("amendment_deadlines"):
        s = iri(r["id"])
        g.t(s, "rdf:type", "pr:AmendmentDeadline")
        if r["act"]:
            g.t(iri(r["act"]), "pr:hasDeadline", s)
        g.t(s, "pr:setIn", iri(r["sitting"]))
        g.t(s, "pr:body", iri(r["body"]) if r["body"] else None)
        g.t(s, "pr:kind", _v(r, "kind"))
        g.t(s, "pr:event", _v(r, "event"))
        g.t(s, "pr:dueDate", _v(r, "due_date", "date"))
        g.t(s, "pr:dueTime", _v(r, "due_time"))
        g.t(s, "pr:evidence", lett(r["sentence"], lingua="it"))
    triple = g.chiudi()
    print(f"grafo: {triple} triple", flush=True)

    v = Grafo(cartella / "parliamentrag_votes.nt.gz", prefissi=False)
    singoli = 0
    for r in tabella("individual_votes"):
        s = iri(f"ballot:{r['vote']}:{r['person']}")
        singoli += 1
        v.t(s, "rdf:type", "pr:IndividualVote")
        v.t(s, "pr:onVote", iri(r["vote"]))
        v.t(s, "pr:voter", iri(r["person"]))
        v.t(s, "pr:outcome", lett(r["result"]))
        v.t(s, "pr:asGroup", iri(r["group"]) if r["group"].startswith("it:") else lett(r["group"]) if r["group"] else None)
    v.chiudi()
    print(f"voti dei singoli: {singoli}", flush=True)
    meta = {"triples": triple, "individual_votes": singoli, "amendments": emendamenti,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    (cartella / "export_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


# ---------- Zenodo ----------

def _zenodo(metodo: str, url: str, token: str, dati: bytes | None = None, tipo: str = "application/json", file: Path | None = None):
    import urllib.request
    if not url.startswith("http"):
        url = "https://zenodo.org/api" + url
    intest = {"Authorization": f"Bearer {token}"}
    corpo = dati
    if file is not None:
        corpo = file.open("rb")
        intest["Content-Length"] = str(file.stat().st_size)
        tipo = "application/octet-stream"
    if corpo is not None:
        intest["Content-Type"] = tipo
    req = urllib.request.Request(url, data=corpo, method=metodo, headers=intest)
    try:
        with urllib.request.urlopen(req, timeout=6 * 3600) as r:
            testo = r.read()
    finally:
        if file is not None:
            corpo.close()
    return json.loads(testo) if testo else None


def bozza_zenodo(cartella: Path, date: dict) -> str:
    """Una nuova versione del record come bozza, con i file e la descrizione nuovi. Non la pubblica."""
    token = env("ZENODO_TOKEN", "")
    if not token:
        raise RuntimeError("manca ZENODO_TOKEN (.env)")
    meta_export = json.loads((cartella / "export_meta.json").read_text())
    trovate = _zenodo("GET", f"/deposit/depositions?q=conceptrecid:{CONCEPT_ZENODO}&all_versions=true&sort=mostrecent&size=5", token)
    aperta = next((d for d in trovate if not d.get("submitted")), None)
    if aperta is None:
        ultima = next(d for d in trovate if d.get("submitted"))
        nuova = _zenodo("POST", f"/deposit/depositions/{ultima['id']}/actions/newversion", token)
        aperta = _zenodo("GET", nuova["links"]["latest_draft"], token)
    else:                                               # nell'elenco manca il link al bucket: serve la scheda intera
        aperta = _zenodo("GET", f"/deposit/depositions/{aperta['id']}", token)
    if "bucket" not in aperta["links"]:
        raise RuntimeError(f"bozza {aperta['id']} senza bucket: file lasciati come sono")
    for f in aperta.get("files", []):
        _zenodo("DELETE", f"/deposit/depositions/{aperta['id']}/files/{f['id']}", token)
    for nome in ("parliamentrag_kg.ttl.gz", "parliamentrag_votes.nt.gz"):
        print(f"carico {nome} su Zenodo", flush=True)
        _zenodo("PUT", f"{aperta['links']['bucket']}/{nome}", token, file=cartella / nome)
    testo = (QUI_MODULO / "zenodo.json").read_text(encoding="utf-8")
    for k, v in {"TRIPLES": f"{meta_export['triples']:,}", "INDIVIDUAL_VOTES": f"{meta_export['individual_votes']:,}",
                 "AMENDMENTS": f"{meta_export['amendments']:,}", "DATI_CAMERA": date.get("camera", ""),
                 "DATI_SENATO": date.get("senato", "")}.items():
        testo = testo.replace("{{" + k + "}}", v)
    metadati = {**aperta["metadata"], **json.loads(testo), "publication_date": dt.date.today().isoformat(),
                "version": dt.date.today().strftime("%Y-%m")}
    _zenodo("PUT", f"/deposit/depositions/{aperta['id']}", token, json.dumps({"metadata": metadati}).encode())
    return aperta["links"]["html"]


# ---------- comando ----------

def main(argv: list[str]) -> int:
    base = QUI / "dati" / "esporta"
    carica = "--senza-caricare" not in argv
    date = ultime_date()
    if "--hf" in argv:
        hf = base / "hf"
        shutil.rmtree(hf, ignore_errors=True)
        scheda_hf(hf, tabelle_hf(hf), date)
        if carica:
            print("Hugging Face:", carica_hf(hf))
    if "--zenodo" in argv:
        rdf = base / "rdf"
        shutil.rmtree(rdf, ignore_errors=True)
        grafo_rdf(rdf)
        if carica:
            print("bozza Zenodo, da pubblicare dal browser:", bozza_zenodo(rdf, date))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
