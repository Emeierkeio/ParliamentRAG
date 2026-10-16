"""Il rapporto: JSON per le macchine (schema/report.v1.json), Markdown per le persone.

Il rapporto non contiene l'ora in cui è stato fatto: la stessa risposta,
con la stessa versione dei dati e del verificatore, dà lo stesso rapporto,
byte per byte.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import List

from .citazioni import ESITI, controlla_citazioni
from .testo import NORMALIZZAZIONI

SCHEMA_RAPPORTO = "https://w3id.org/parliamentrag/verify/report/v1"
NOME = "parliamentrag-verifica"


def impronta(risposta: dict) -> str:
    """sha256 della risposta in JSON canonico (chiavi ordinate, UTF-8)."""
    testo = json.dumps(risposta, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()


def _avvisi(risposta: dict, dati: dict) -> List[dict]:
    out = []
    chiesta, usata = risposta.get("data_version"), dati.get("version")
    if chiesta and usata and chiesta not in (usata, dati.get("revision")):
        out.append({"code": "data_version_differs",
                    "detail": f"la risposta usa i dati {chiesta}, la verifica i dati {usata}"})
    camere = set(dati.get("chambers") or [])
    for c in risposta.get("claims") or []:
        camera = "senato" if str(c.get("speech", "")).startswith("sen_") else "camera"
        if camere and camera not in camere:
            out.append({"code": "chamber_not_in_data",
                        "detail": f"i dati usati non contengono il {'Senato' if camera == 'senato' else 'la Camera'}"})
            break
    return out


def crea(risposta: dict, fonte, versione: str) -> dict:
    """Il rapporto JSON delle citazioni."""
    dati = fonte.versione()
    voci = controlla_citazioni(risposta, fonte)
    conteggio = Counter(v["outcome"] for v in voci)
    non_verificabili = Counter(nome for v in voci for nome, stato in v["checks"].items()
                               if stato == "not_verifiable")
    risposta_info = {
        "system": risposta.get("system") or {},
        "question": risposta.get("question") or "",
        "data_version": risposta.get("data_version") or "",
        "claims": len(voci),
        "sha256": impronta(risposta),
    }
    if risposta.get("generated_at"):
        risposta_info["generated_at"] = risposta["generated_at"]
    return {
        "schema": SCHEMA_RAPPORTO,
        "verifier": {"name": NOME, "version": versione},
        "rules": {"format": 1, "quote_normalizations": list(NORMALIZZAZIONI)},
        "data": dati,
        "answer": risposta_info,
        "warnings": _avvisi(risposta, dati),
        "quotes": {
            "total": len(voci),
            "exact": conteggio["esatta"] + conteggio["esatta_dopo_normalizzazione"],
            "by_outcome": {e: conteggio[e] for e in ESITI if conteggio[e]},
            "not_verifiable": dict(sorted(non_verificabili.items())),
            "items": voci,
        },
    }


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

_MOTIVI = {
    "unknown_speech_id_format": "l'ID dell'intervento non ha il formato del dataset",
    "speech_not_in_sitting": "la seduta c'è, l'intervento no",
    "sitting_not_in_data": "la seduta non è in questa versione dei dati",
    "not_in_data": "l'intervento non è in questa versione dei dati",
    "not_in_speech_text": "non compare nel testo dell'intervento",
    "opens_with_quotation_marks": "si apre con delle virgolette: sono parole di altri",
    "inside_quotation_marks": "nel resoconto sta dentro delle virgolette: l'oratore riporta parole di altri",
    "attributed_to_someone_else": "nel resoconto l'oratore le attribuisce a un'altra persona",
    "speech_has_no_speaker": "il resoconto non dice chi parla",
    "different_speaker": "nel resoconto parla un'altra persona",
    "not_in_government_on_date": "alla data dell'intervento la persona non era al Governo",
    "misto_instead_of_component": "indica il Misto: va indicata la componente",
    "other_group_on_date": "alla data dell'intervento la persona era in un altro gruppo",
    "no_membership_on_date": "i dati non dicono in che gruppo fosse la persona a quella data",
    "membership_without_uri": "il gruppo della persona a quella data non ha un URI nei dati",
    "speech_has_no_date": "l'intervento non ha una data",
    "not_a_url": "non è un indirizzo web",
    "wrong_site": "non porta al sito della camera giusta",
    "wrong_page": "non porta al resoconto",
    "wrong_sitting": "porta a un'altra seduta",
    "wrong_legislature": "porta a un'altra legislatura",
    "not_the_record": "non porta al resoconto stenografico",
    "wrong_anchor": "porta a un altro punto del resoconto",
}

_ESITI_IT = {
    "esatta": "esatta",
    "esatta_dopo_normalizzazione": "esatta dopo normalizzazione",
    "non_trovata": "non trovata",
    "parole_di_terzi": "parole di terzi",
    "oratore_errato": "oratore errato",
    "gruppo_errato": "gruppo errato",
    "link_errato": "link errato",
    "intervento_inesistente": "intervento inesistente",
}

_NORMALIZZAZIONI_IT = {"whitespace": "spazi", "first_letter_case": "maiuscola iniziale",
                       "typographic_apostrophe": "apostrofi tipografici"}
_CONTROLLO_PER_ESITO = {"intervento_inesistente": "speech", "non_trovata": "text", "parole_di_terzi": "own_words",
                        "oratore_errato": "speaker", "gruppo_errato": "group", "link_errato": "link"}
_CONTROLLI_IT = {"speech": "intervento", "text": "testo", "own_words": "parole proprie", "speaker": "oratore",
                 "group": "gruppo", "link": "link"}


def _breve(testo: str, n: int = 90) -> str:
    t = " ".join(testo.split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def markdown(r: dict) -> str:
    d, a, q = r["data"], r["answer"], r["quotes"]
    revisione = f"@{d['revision'][:8]}" if d.get("revision") else ""
    fonte = d.get("dataset") or d.get("source")
    righe = [
        f"Verifica ParliamentRAG v{r['verifier']['version']} · dati {d.get('version') or '?'} ({fonte}{revisione})",
        "",
        f"Risposta   {a['system'].get('name', '?')} · «{_breve(a['question'], 80)}» · dati {a['data_version']}",
    ]
    for w in r["warnings"]:
        righe.append(f"Attenzione  {w.get('detail') or w['code']}")
    righe.append("")
    if not q["total"]:
        righe.append("Citazioni   nessuna citazione da controllare")
    else:
        righe.append(f"Citazioni   {q['exact']} su {q['total']} esatte")
    for v in q["items"]:
        esito = v["outcome"]
        if esito in ("esatta", "esatta_dopo_normalizzazione"):
            continue
        controllo = _CONTROLLO_PER_ESITO[esito]
        motivo = _MOTIVI.get(v["reasons"].get(controllo, ""), v["reasons"].get(controllo, ""))
        righe.append(f"  ✗ #{v['index']}  {esito}: «{_breve(v['quote'], 70)}» · {v['speech']}" + (f" · {motivo}" if motivo else ""))
    per_regole: dict = {}
    for v in q["items"]:
        if v["outcome"] == "esatta_dopo_normalizzazione":
            per_regole.setdefault(tuple(v["normalizations"]), []).append(v["index"])
    for regole, indici in per_regole.items():
        nomi = " e ".join(_NORMALIZZAZIONI_IT[x] for x in regole)
        quante = "1 esatta" if len(indici) == 1 else f"{len(indici)} esatte"
        righe.append(f"  ~ {quante} dopo normalizzazione ({nomi}): " + ", ".join(f"#{i}" for i in indici))
    for v in q["items"]:
        aperti = [c for c, s in v["checks"].items() if s == "not_verifiable"]
        for c in aperti:
            motivo = _MOTIVI.get(v["reasons"].get(c, ""), v["reasons"].get(c, ""))
            righe.append(f"  ? #{v['index']}  {_CONTROLLI_IT[c]} non verificabile: {motivo}")
    if q["by_outcome"]:
        righe.append("")
        righe.append("Esiti       " + ", ".join(f"{_ESITI_IT[e]} {n}" for e, n in q["by_outcome"].items()))
    righe.append("")
    righe.append("Regole      citazione letterale; ammessi solo spazi multipli, maiuscola della prima lettera e apostrofi tipografici")
    return "\n".join(righe) + "\n"
