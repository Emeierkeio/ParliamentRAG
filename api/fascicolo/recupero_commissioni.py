"""Le commissioni di un tema: quelle a cui sono assegnati in sede referente i progetti di legge più vicini alla domanda,
con le parole chiave delle commissioni (commissioni_temi.json) quando i progetti non bastano o il ramo non ha le
assegnazioni (oggi il Senato). Serve a mostrarle nel fascicolo; non cambia le evidenze.

Votano solo i progetti con coseno almeno MINIMA ed entro MARGINE dal più vicino, e la prima commissione deve avere
QUOTA_PRIMA dei voti: una domanda su cui nessun titolo è centrato sparpaglia i voti e passa alle parole chiave.

MINIMA è ritarata per text-embedding-3-large (era 0,30 col 3-small) sulle 35 domande della prova pilota più 5 fuori
dominio (benchmark/pilota-2026-11-02, 4/11/2026): il titolo più vicino sta fra 0,46 e 0,61 per le domande su un tema
di legge (separazione delle carriere, legge elettorale, Ucraina, lavoro, sanità), fra 0,37 e 0,45 per quelle che non lo
hanno (voti, cofirme, applausi), fra 0,30 e 0,42 fuori dominio. Con 0,30 una domanda sulla carbonara finiva alla
Commissione Giustizia. MARGINE resta 0,08: fra i titoli sul tema e gli altri ci sono circa 0,1-0,15 di coseno anche
col modello nuovo. Le quote sono parti dei voti, non similarità: restano quelle del backend precedente."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import psycopg

from . import modello

PROGETTI, MINIMA, MARGINE, QUOTA_PRIMA, QUOTA = 20, 0.45, 0.08, 0.40, 0.25
LEGISLATURA = 19
_PAROLA = re.compile(r"\w+", re.UNICODE)
_PERMANENTE_CAMERA = re.compile(r"^[IVX]+ COMMISSIONE\b", re.IGNORECASE)

# la commissione permanente del Senato che copre ciascuna della Camera (XIX: dieci commissioni dopo la riforma del 2022)
SENATO = {
    "I": "1ª Commissione permanente (Affari Costituzionali)",
    "II": "2ª Commissione permanente (Giustizia)",
    "III": "3ª Commissione permanente (Affari esteri e difesa)",
    "IV": "3ª Commissione permanente (Affari esteri e difesa)",
    "V": "5ª Commissione permanente (Bilancio)",
    "VI": "6ª Commissione permanente (Finanze e tesoro)",
    "VII": "7ª Commissione permanente (Cultura e patrimonio culturale, istruzione pubblica)",
    "VIII": "8ª Commissione permanente (Ambiente, transizione ecologica, energia, lavori pubblici, comunicazioni, innovazione tecnologica)",
    "IX": "8ª Commissione permanente (Ambiente, transizione ecologica, energia, lavori pubblici, comunicazioni, innovazione tecnologica)",
    "X": "9ª Commissione permanente (Industria, commercio, turismo, agricoltura e produzione agroalimentare)",
    "XI": "10ª Commissione permanente (Affari sociali, sanità, lavoro pubblico e privato, previdenza sociale)",
    "XII": "10ª Commissione permanente (Affari sociali, sanità, lavoro pubblico e privato, previdenza sociale)",
    "XIII": "9ª Commissione permanente (Industria, commercio, turismo, agricoltura e produzione agroalimentare)",
    "XIV": "4ª Commissione permanente (Politiche dell'Unione europea)",
}

# radici rozze di alcune parole dei temi (sanitario/sanità → sanit)
_RADICI = [("sanitari", "sanit"), ("salute", "salut"), ("sanità", "sanit"), ("lavoro", "lavor"), ("lavorator", "lavor"),
           ("giustizia", "giustiz"), ("giudiziario", "giudiz"), ("ambiente", "ambient"), ("ambientale", "ambient"),
           ("difesa", "difes"), ("immigrazion", "immigr"), ("migrant", "migr"), ("scuola", "scuol"),
           ("scolastic", "scol"), ("istruzion", "istruz"), ("educazion", "educ")]


@lru_cache(maxsize=1)
def temi() -> dict[str, list[str]]:
    """Le parole chiave di ogni commissione e comitato della Camera (nome -> parole)."""
    return json.loads((Path(__file__).parent / "commissioni_temi.json").read_text(encoding="utf-8"))


def _radici(t: str) -> str:
    t = t.lower()
    for coda, radice in _RADICI:
        if coda in t:
            t = t.replace(coda, radice)
    return t


def _romano(nome: str) -> str:
    return nome.split(" ", 1)[0].upper()


def per_parole(domanda: str, quante: int = 3, minimo: float = 0.1, rami: tuple[str, ...] = ("camera",)) -> list[dict]:
    """Le commissioni permanenti della Camera con parole chiave nella domanda (parola intera, o radice di almeno 4
    lettere), ciascuna riportata in ogni ramo chiesto. Punteggio 0,5 per una parola più 0,2 per ogni altra, fino a 1."""
    bassa, norm = domanda.lower(), _radici(domanda)
    parole_domanda = set(_PAROLA.findall(norm))
    trovate = []
    for nome, chiavi in temi().items():
        if not _PERMANENTE_CAMERA.match(nome):
            continue
        prese = []
        for k in chiavi:
            parole_k = _PAROLA.findall(_radici(k))
            # parola intera: «NATO» non vale dentro «Senato»
            if re.search(r"(?<!\w)" + re.escape(k.lower()) + r"(?!\w)", bassa):
                prese.append(k)
            elif any(pk in parole_domanda or any(q.startswith(pk) or pk.startswith(q) for q in parole_domanda if len(q) >= 4)
                     for pk in parole_k if len(pk) >= 4):
                prese.append(k)
        if prese:
            trovate.append((nome, min(1.0, 0.5 + 0.2 * (len(prese) - 1)), prese))
    trovate.sort(key=lambda x: x[1], reverse=True)
    out, senato_visto = [], set()
    for nome, punti, prese in trovate[:quante]:
        if punti < minimo:
            continue
        voce = {"score": round(punti, 2), "matched_keywords": prese, "categories": [], "all_keywords": temi()[nome][:5]}
        if "camera" in rami:
            out.append({"nome": nome, "chamber": "camera", **voce})
        sen = SENATO.get(_romano(nome))
        if "senato" in rami and sen and sen not in senato_visto:
            senato_visto.add(sen)
            out.append({"nome": sen, "chamber": "senato", **voce})
    return out


def _nome_esteso(nome_organo: str) -> str:
    """«XII Commissione» -> il nome delle parole chiave («XII COMMISSIONE (AFFARI SOCIALI)»), se c'è."""
    r = _romano(nome_organo)
    return next((n for n in temi() if _PERMANENTE_CAMERA.match(n) and _romano(n) == r), nome_organo)


def progetti_vicini(c: psycopg.Connection, vettore: str, ramo: str, quanti: int = PROGETTI) -> list[dict]:
    """I progetti di legge del ramo assegnati in sede referente a una commissione permanente, più vicini alla domanda
    per il titolo (coseno), con le loro commissioni. Ricerca esatta: sono qualche migliaio."""
    with c.transaction():
        c.execute("SET LOCAL statement_timeout = '30s'")
        return c.execute("""
            WITH b AS (
              SELECT a.uri, a.number, array_agg(DISTINCT o.name ORDER BY o.name) AS commissioni
              FROM act a JOIN act_assignment x ON x.act = a.uri AND x.seat = 'referente'
              JOIN body o ON o.uri = x.body AND o.name ~* '^[IVX]+ commissione\\M'
              WHERE a.chamber = %(r)s AND a.legislature = %(leg)s AND a.kind = 'bill'
              GROUP BY a.uri, a.number)
            SELECT b.uri, b.number, b.commissioni, max(1 - (v.embedding <=> %(q)s::halfvec(1024))) AS cos
            FROM b JOIN passage p ON p.source = 'act_title' AND p.uri = b.uri
            JOIN act_vector v ON v.hash = p.hash AND v.model = %(m)s
            GROUP BY b.uri, b.number, b.commissioni ORDER BY cos DESC LIMIT %(k)s""",
            {"r": ramo, "leg": LEGISLATURA, "q": vettore, "m": modello.MODELLO_VETTORI, "k": quanti}).fetchall()


def classifica(progetti: list[dict], ramo: str, quante: int = 3) -> list[dict]:
    """Le commissioni votate dai progetti vicini, pesate per similarità; [] se nessun progetto è abbastanza vicino o i
    più vicini non sono d'accordo su una commissione."""
    if not progetti:
        return []
    soglia = max(MINIMA, float(progetti[0]["cos"]) - MARGINE)
    pesi: dict[str, float] = defaultdict(float)
    sostegno: dict[str, list[str]] = defaultdict(list)
    for b in progetti:
        if float(b["cos"]) < soglia:
            break
        quota = float(b["cos"]) / len(b["commissioni"])          # le riunite si dividono il voto
        for nome in b["commissioni"]:
            pesi[nome] += quota
            sostegno[nome].append(str(b["number"]))
    totale = sum(pesi.values())
    if totale <= 0:
        return []
    ordine = sorted(pesi.items(), key=lambda kv: -kv[1])
    if ordine[0][1] / totale < QUOTA_PRIMA:
        return []
    out = []
    for i, (nome, w) in enumerate(ordine[:quante]):
        punti = w / totale
        if i > 0 and punti < QUOTA:
            break
        out.append({"nome": _nome_esteso(nome), "chamber": ramo, "score": round(punti, 2), "matched_keywords": [],
                    "categories": [], "all_keywords": [], "method": "bills", "bills": sostegno[nome][:5]})
    return out


def commissioni(c: psycopg.Connection, domanda: str, vettore: str | None, rami: tuple[str, ...] = ("camera",),
                riscritta: str | None = None, quante: int = 3) -> list[dict]:
    """Le commissioni del tema per ramo, prima la Camera: dai progetti di legge vicini, o dalle parole chiave (della
    domanda, poi della domanda riscritta) per un ramo in cui i progetti non decidono."""
    out: list[dict] = []
    parole: list[dict] | None = None
    for ramo in ("camera", "senato"):
        if ramo not in rami:
            continue
        trovate = classifica(progetti_vicini(c, vettore, ramo), ramo, quante) if vettore else []
        if not trovate:
            if parole is None:
                parole = per_parole(domanda, quante, 0.1, tuple(rami))
                if not parole and riscritta:
                    parole = per_parole(riscritta, quante, 0.1, tuple(rami))
            trovate = [{**x, "method": "keywords"} for x in parole if x["chamber"] == ramo]
        out += trovate
    return out
