"""I due canali del recupero sul Postgres v3: il denso (vicini della domanda fra i brani, pgvector su passage_vector) e
quello degli atti (atti sul tema, chi li ha firmati, i brani dei loro interventi vicini alla domanda).

Le similarità sono sulla scala del backend precedente, coseno portato in [0, 1] come (1 + cos) / 2: le soglie della
configurazione restano confrontabili. In pgvector `<=>` è la distanza coseno (1 - cos), quindi similarità = 1 - d/2."""

from __future__ import annotations

import datetime as dt
import re

import psycopg

from ..strumenti.comune import url_intervento, url_sedute
from . import modello
from .recupero_gruppi import GOVERNO, MISTO, NOME_GOVERNO, componente_senato, e_misto, lato_di, partito

LEGISLATURA = 19
# la ricerca sull'indice HNSW: con i filtri (fonte, ramo, date, persone) l'indice continua a scorrere finché non trova
# k brani buoni (iterative scan di pgvector 0.8), fino a MAX_TUPLE vettori
EF_MINIMO, EF_MASSIMO, MAX_TUPLE = 100, 1000, 200_000
TEMPO_MASSIMO = "30s"                                   # per le query pesanti; il ruolo `lettura` ne ha 8

# chi presiede non prende posizione; i membri del governo si riconoscono dalla carica dichiarata (Senato) o dall'assenza
# del gruppo nel resoconto (Camera), con un incarico di governo alla data
CARICA_GOVERNO = r"\m(ministr|vice ?ministr|sottosegretari|presidente del consiglio)"


def similarita(distanza: float) -> float:
    """Dalla distanza coseno di pgvector alla scala (1 + cos) / 2."""
    return 1.0 - float(distanza) / 2.0


def _imposta(c: psycopg.Connection, k: int) -> None:
    """Parametri di sessione per una ricerca dei vicini, validi fino alla fine della transazione."""
    ef = max(EF_MINIMO, min(EF_MASSIMO, k))
    c.execute(f"SET LOCAL statement_timeout = '{TEMPO_MASSIMO}'")
    c.execute(f"SET LOCAL hnsw.ef_search = {ef}")
    c.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
    c.execute(f"SET LOCAL hnsw.max_scan_tuples = {MAX_TUPLE}")


def vicini(c: psycopg.Connection, vettore: list[float] | str, fonti: list[str], k: int, *,
           rami: list[str] | None = None, da: dt.date | None = None, a: dt.date | None = None,
           persone: list[str] | None = None, solo_parlamentari: bool = False, sommari: bool = True,
           uris: list[str] | None = None) -> list[dict]:
    """I k brani più vicini al vettore fra quelli delle fonti date (passage.source: speech, act, act_title, act_text,
    document, amendment, profession, education, body), dal più vicino.

    Filtri, tutti facoltativi: `rami` (camera, senato: per gli interventi il ramo della seduta, per le altre fonti il
    prefisso dell'uri), `uris` (solo quei testi). Solo per gli interventi: `da`/`a` (data della seduta, estremi
    inclusi), `persone` (uri di chi parla), `solo_parlamentari` (via chi presiede e chi non ha una scheda, come gli
    auditi), `sommari=False` (via i resoconti sommari, che non sono parole testuali).

    Ogni riga: source, uri, ord, start_char, end_char, hash, similarita (scala (1 + cos) / 2)."""
    if not fonti or k <= 0:
        return []
    letterale = vettore if isinstance(vettore, str) else modello.letterale(vettore)
    interventi = set(fonti) == {"speech"}
    if not interventi and (da or a or persone or solo_parlamentari or not sommari):
        raise ValueError("date, persone e sommari filtrano solo gli interventi (fonti=['speech'])")
    dove, par = ["v.model = %(m)s", "p.source = ANY(%(f)s)"], {"m": modello.MODELLO_VETTORI, "f": list(fonti),
                                                               "q": letterale, "k": int(k)}
    unisci = ""
    if interventi:
        unisci = "JOIN speech s ON s.uri = p.uri JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting"
        if rami:
            dove.append("st.chamber = ANY(%(r)s)")
        if da:
            dove.append("st.date >= %(da)s")
        if a:
            dove.append("st.date <= %(a)s")
        if persone:
            dove.append("s.person = ANY(%(pers)s)")
        if solo_parlamentari:
            dove.append("s.person IS NOT NULL AND s.as_office IS DISTINCT FROM 'PRESIDENTE'")
        if not sommari:
            dove.append("s.kind IS DISTINCT FROM 'summary'")
    elif rami:
        # act_text ha per chiave il codice dello stampato (leg.19.pdl.camera.3148…), le altre fonti un uri it:<ramo>:…
        dove.append("(split_part(p.uri, ':', 2) = ANY(%(r)s) OR p.uri ~ ('\\.(' || array_to_string(%(r)s, '|') || ')\\.'))")
    if uris is not None:
        dove.append("p.uri = ANY(%(u)s)")
    par.update(r=list(rami or []), da=da, a=a, pers=list(persone or []), u=list(uris or []))
    sql = f"""
        WITH x AS MATERIALIZED (
          SELECT p.source, p.uri, p.ord, p.start_char, p.end_char, p.hash, v.embedding <=> %(q)s::halfvec(1024) AS d
          FROM passage_vector v JOIN passage p ON p.hash = v.hash {unisci}
          WHERE {' AND '.join(dove)}
          ORDER BY v.embedding <=> %(q)s::halfvec(1024)
          LIMIT %(k)s)
        SELECT * FROM x ORDER BY d, source, uri, ord"""
    with c.transaction():
        _imposta(c, k)
        if interventi and "camera" in (rami or ["camera"]) and not (da or a or persone or uris):
            # filtri larghi (gli interventi della Camera, o dei due rami, senza date né persone): il planner sottostima
            # quanti brani passano il filtro sulle sedute e a volte sceglie la lettura esatta (4-6 s contro 0,3-1 s
            # dell'indice). Con il Senato solo (5% dei vettori) o con date e persone la lettura esatta è giusta: l'indice
            # si fermerebbe a MAX_TUPLE con meno di k brani (EXPLAIN ANALYZE del 4/11/2026)
            c.execute("SET LOCAL enable_sort = off")
        righe = c.execute(sql, par).fetchall()
    for r in righe:
        r["similarita"] = similarita(r.pop("d"))
    return righe


# gli interventi dei brani, con chi parla, la seduta e il gruppo alla data. Le schede segnaposto del Senato (membri del
# governo senza anagrafica del Senato) si leggono con la scheda della Camera a cui sono legate.
# - gruppo alla data: group_at (la componente del Misto prima del Misto); `alto` è il gruppo (il Misto per una componente)
# - oggi: chi parla è ancora nello stesso gruppo oggi (una citazione non si dà mai a un gruppo che ha lasciato)
# - governo: un incarico di governo alla data (anche con l'altra scheda) e la carica nel resoconto, o nessun gruppo
#   dichiarato nell'Aula della Camera
SQL_INTERVENTI = """
WITH s0 AS (
  SELECT s.uri, s.person AS fonte, s.text, s.kind, s.as_group, s.as_office, s.speaker_label,
         st.uri AS sitting, st.chamber, st.date, st.number, st.kind AS sitting_kind, st.body_name, i.title AS debate,
         coalesce((SELECT x.person FROM person_same_as x JOIN person p0 ON p0.uri = s.person AND p0.stub
                   WHERE x.same_as = s.person ORDER BY x.person LIMIT 1), s.person) AS persona
  FROM speech s JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
  WHERE s.uri = ANY(%(uris)s)),
s1 AS (
  SELECT s0.*, group_at(s0.persona, s0.date) AS g FROM s0)
SELECT s1.*, p.given_name, p.family_name,
       g.name AS g_name, g.short_name AS g_short, g.kind AS g_kind,
       coalesce(alto.uri, g.uri) AS alto, coalesce(alto.name, g.name) AS alto_name, coalesce(alto.short_name, g.short_name) AS alto_short,
       EXISTS (SELECT 1 FROM membership m WHERE m.person = s1.persona AND m.grp = coalesce(alto.uri, g.uri)
               AND m.start_date <= s1.date AND (m.end_date IS NULL OR m.end_date >= current_date)) AS oggi,
       EXISTS (SELECT 1 FROM office o
               WHERE o.person IN (SELECT s1.persona UNION SELECT s1.fonte
                                  UNION SELECT same_as FROM person_same_as WHERE person = s1.persona
                                  UNION SELECT person FROM person_same_as WHERE same_as = s1.persona)
                 AND o.target LIKE 'it:gov:%%' AND o.start_date <= s1.date AND (o.end_date IS NULL OR o.end_date >= s1.date))
         AND (s1.as_office ~* %(carica)s OR (s1.as_group IS NULL AND s1.sitting_kind = 'assembly_verbatim'))
         AS governo
FROM s1 LEFT JOIN person p ON p.uri = s1.persona
LEFT JOIN grp g ON g.uri = s1.g
LEFT JOIN grp alto ON alto.uri = g.part_of
"""


def _nome(given: str | None, family: str | None, etichetta: str | None) -> str:
    nome = " ".join(x for x in (given, family) if x)
    if not nome:
        nome = (etichetta or "").split(",")[0]
    return nome.title() if nome.isupper() else nome


def _titolo(t: str | None) -> str | None:
    """Il titolo dell'argomento senza gli orari ripetuti («(ore 12,27). (ore 12,27)»)."""
    if not t:
        return None
    t = re.sub(r"\s*\(ore \d{1,2}[,.]\d{2}\)\.?", "", t).strip()
    return t or None


def interventi(c: psycopg.Connection, brani: list[dict], attesi: dict[str, dict]) -> list[dict]:
    """I brani di interventi come candidati del fascicolo, nell'ordine dato, con chi parla e il gruppo alla data.

    Ogni candidato ha `partito` (per chi conta oggi: il gruppo alla data ancora in corso oggi, la componente per il
    Misto; None se ha cambiato gruppo da allora), `partito_data` (il gruppo alla data, anche se l'ha lasciato), `lato`
    e `governo`. Il brano è il testo fra start_char e end_char dell'intervento."""
    uris = sorted({b["uri"] for b in brani if b.get("source", "speech") == "speech"})
    if not uris:
        return []
    with c.transaction():
        c.execute(f"SET LOCAL statement_timeout = '{TEMPO_MASSIMO}'")
        info = {r["uri"]: r for r in c.execute(SQL_INTERVENTI, {"uris": uris, "carica": CARICA_GOVERNO})}
        # il resoconto del Senato non ha ancore stabili: il link è la pagina della seduta, se la pipeline l'ha scritta
        resoconti = url_sedute(c, [r["sitting"] for r in info.values() if r["chamber"] != "camera"])
    out = []
    for b in brani:
        r = info.get(b["uri"])
        if r is None:
            continue
        componente = r["g_name"] if r["g_kind"] == "misto_component" else None
        sigla = r["g_short"]
        nome_partito = partito(componente or r["alto_name"]) if r["alto"] else None
        if r["alto"] and e_misto(r["alto_name"]) and not componente and r["chamber"] == "senato":
            # Misto del Senato senza componenti in anagrafica: la componente dal resoconto («Misto-AVS»)
            componente, p_sen = componente_senato(r["as_group"])
            if p_sen:
                nome_partito, sigla = p_sen, r["as_group"]
        governo = bool(r["governo"])
        partito_oggi = nome_partito if r["oggi"] else None
        if governo:
            partito_oggi, lato = partito_oggi or NOME_GOVERNO, GOVERNO
        elif nome_partito in attesi:
            lato = attesi[nome_partito]["lato"]
        elif componente or e_misto(nome_partito):
            lato = MISTO
        else:
            lato = lato_di(nome_partito, attesi)
        testo = r["text"][b["start_char"]:b["end_char"]]
        out.append({
            "chunk_id": f"{b['uri']}#{b['ord']}",
            "speech_uri": b["uri"],
            "ord": b["ord"],
            "start_char": b["start_char"], "end_char": b["end_char"],
            "text": testo,
            "speech_text": r["text"],
            "kind": r["kind"] or "verbatim",
            "speaker": {"uri": r["persona"], "nome": _nome(r["given_name"], r["family_name"], r["speaker_label"]),
                        "gruppo": r["alto_name"], "sigla": sigla, "componente": componente,
                        "ruolo": "governo" if governo else ("deputato" if r["chamber"] == "camera" else "senatore"),
                        "carica": r["as_office"] if r["as_office"] not in (None, "senatore") else None},
            "partito": partito_oggi,
            "partito_data": NOME_GOVERNO if governo and not nome_partito else nome_partito,
            "lato": lato,
            "governo": governo,
            "chamber": r["chamber"],
            "date": r["date"].isoformat(),
            "sitting": r["sitting"],
            "sitting_number": r["number"],
            "sitting_kind": r["sitting_kind"],
            "body": r["body_name"],
            "debate": _titolo(r["debate"]),
            "url": url_intervento(b["uri"], resoconti.get(r["sitting"])),
            "similarita": b["similarita"],
            "canali": [],
        })
    return out


# --- canale degli atti -------------------------------------------------------------------------------------------

# parole vuote italiane, più quelle frequenti nelle domande («posizione», «partiti») e nella domanda del sito sui temi
# («Qual è la posizione dei gruppi parlamentari sul tema: X?»)
PAROLE_VUOTE = {
    "il", "la", "lo", "i", "gli", "le", "un", "una", "uno",
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
    "del", "della", "dello", "dei", "degli", "delle",
    "al", "alla", "allo", "ai", "agli", "alle",
    "dal", "dalla", "dallo", "dai", "dagli", "dalle",
    "nel", "nella", "nello", "nei", "negli", "nelle",
    "sul", "sulla", "sullo", "sui", "sugli", "sulle",
    "col", "coi",
    "e", "o", "ma", "che", "chi", "cui", "quale", "quali",
    "come", "dove", "quando", "perché", "quanto",
    "è", "sono", "essere", "stato", "stata", "stati", "state",
    "ha", "hanno", "avere", "aveva", "avevano",
    "si", "non", "più", "anche", "già", "poi", "però", "quindi",
    "qual", "cosa", "posizione", "partiti", "partito",
    "query", "originale",
    "gruppi", "gruppo", "parlamentari", "tema",
}


def parole_chiave(domanda: str) -> list[str]:
    """Parole della domanda senza le parole vuote (più di due lettere), poi al massimo 5 coppie di parole vicine."""
    parole = re.findall(r"\b\w+\b", domanda.lower())
    singole = list(dict.fromkeys(w for w in parole if w not in PAROLE_VUOTE and len(w) > 2))
    coppie = list(dict.fromkeys(f"{parole[i]} {parole[i + 1]}" for i in range(len(parole) - 1)
                                if parole[i] not in PAROLE_VUOTE and parole[i + 1] not in PAROLE_VUOTE))
    return singole + coppie[:5]


def _modello_re(parola: str) -> str:
    """Espressione regolare di Postgres per la parola intera, senza maiuscole."""
    return r"\m" + re.sub(r"([\\.^$|?*+()\[\]{}])", r"\\\1", parola) + r"\M"


def atti_per_parole(c: psycopg.Connection, parole: list[str], rami: list[str], quanti: int) -> list[dict]:
    """Gli atti dei rami con una delle parole (parola intera) nel titolo, nella descrizione o nei temi EuroVoc. Prima
    quelli con più parole diverse, poi i più recenti."""
    if not parole:
        return []
    sql = """
        WITH m AS (SELECT x.m FROM unnest(%(re)s::text[]) x(m)),
        t AS (SELECT a.uri, m.m FROM act a JOIN m ON a.title ~* m.m OR coalesce(a.description, '') ~* m.m
              WHERE a.legislature = %(leg)s AND a.chamber = ANY(%(rami)s)),
        e AS (SELECT s.act AS uri, m.m FROM concept k JOIN m ON k.label_it ~* m.m JOIN act_subject s ON s.concept = k.uri),
        h AS (SELECT uri, count(DISTINCT m) AS conta FROM (SELECT * FROM t UNION ALL SELECT * FROM e) z GROUP BY uri)
        SELECT a.uri, a.chamber, a.kind, a.number, a.title, a.date, h.conta
        FROM h JOIN act a ON a.uri = h.uri
        WHERE a.legislature = %(leg)s AND a.chamber = ANY(%(rami)s)
        ORDER BY h.conta DESC, a.date DESC NULLS LAST, a.uri
        LIMIT %(n)s"""
    par = {"re": [_modello_re(p) for p in parole], "leg": LEGISLATURA, "rami": list(rami), "n": int(quanti)}
    with c.transaction():
        c.execute(f"SET LOCAL statement_timeout = '{TEMPO_MASSIMO}'")
        return c.execute(sql, par).fetchall()


def similarita_atti(c: psycopg.Connection, vettore: str, uris: list[str]) -> dict[str, float]:
    """La similarità più alta fra la domanda e i brani di ogni atto (titolo dei progetti di legge, testo degli atti di
    indirizzo e controllo), in coseno puro come nel backend precedente."""
    if not uris:
        return {}
    with c.transaction():
        c.execute(f"SET LOCAL statement_timeout = '{TEMPO_MASSIMO}'")
        righe = c.execute("""
            SELECT p.uri, max(1 - (v.embedding <=> %(q)s::halfvec(1024))) AS cos
            FROM passage p JOIN passage_vector v ON v.hash = p.hash AND v.model = %(m)s
            WHERE p.source IN ('act', 'act_title') AND p.uri = ANY(%(u)s) GROUP BY p.uri""",
            {"q": vettore, "m": modello.MODELLO_VETTORI, "u": list(uris)}).fetchall()
    return {r["uri"]: float(r["cos"]) for r in righe}


def firmatari(c: psycopg.Connection, atti: list[str]) -> list[str]:
    """Chi ha firmato gli atti (primo firmatario e cofirmatari), con tutte le sue schede (Camera e Senato)."""
    if not atti:
        return []
    righe = c.execute("""
        WITH f AS (SELECT DISTINCT person FROM act_sponsor WHERE act = ANY(%(a)s))
        SELECT person AS u FROM f
        UNION SELECT same_as FROM person_same_as WHERE person IN (SELECT person FROM f)
        UNION SELECT person FROM person_same_as WHERE same_as IN (SELECT person FROM f)""", {"a": list(atti)}).fetchall()
    return sorted(r["u"] for r in righe)
