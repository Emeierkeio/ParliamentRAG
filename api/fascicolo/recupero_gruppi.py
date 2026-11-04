"""Gruppi del recupero: il partito per cui conta un intervento, i partiti attesi in una risposta e il loro lato.

Un partito è il nome con cui un gruppo compare nel fascicolo, lo stesso nei due rami: il PD della Camera e quello del
Senato sono un partito solo, e «tutti i gruppi» lo conta una volta. Il nome è quello del gruppo della Camera; i gruppi
del Senato con un nome diverso e le componenti del Misto che portano il nome di un gruppo (AVS e Noi Moderati alla
Camera fino al 27/10/2022, AVS e Azione al Senato) si legano al gruppo. Le altre componenti del Misto (+Europa, Futuro
Nazionale…) sono partiti a sé, nel blocco del Misto: un intervento del Misto conta sempre per la sua componente, mai per
il Misto intero.

Lo schieramento viene dalla regola unica di maggioranza.py (voti di fiducia dei dodici mesi, riserva: membri al
governo), contando insieme i gruppi dello stesso partito nei due rami. Il lato con cui il fascicolo dispone i partiti è
lo schieramento, salvo il Misto e le componenti che sono partiti a sé: quelli stanno nel blocco del Misto (lato
«misto»), qualunque sia il loro schieramento, che resta in `schieramento`. I partiti attesi restano in memoria per
DURATA secondi, come nel backend precedente."""

from __future__ import annotations

import re
import threading
import time

import psycopg

from . import maggioranza

LEGISLATURA = 19
MAGGIORANZA, OPPOSIZIONE, MISTO, GOVERNO = maggioranza.MAGGIORANZA, maggioranza.OPPOSIZIONE, maggioranza.MISTO, maggioranza.GOVERNO
NOME_MISTO, NOME_GOVERNO = "Misto", "Governo"
DURATA = 6 * 3600


def chiave(nome: str | None) -> str:
    """Nome confrontabile: maiuscole, apostrofi dritti, trattini senza spazi, spazi singoli."""
    t = (nome or "").upper().replace("’", "'")
    t = re.sub(r"\s*[-–—]\s*", "-", t)
    return " ".join(t.split())


# gruppi del Senato e componenti del Misto che sono lo stesso partito di un gruppo della Camera (nome della Camera)
_STESSO_PARTITO = {
    "LEGA SALVINI PREMIER-PARTITO SARDO D'AZIONE": "Lega - Salvini Premier",
    "CIVICI D'ITALIA-UDC-NOI MODERATI (NOI CON L'ITALIA, CORAGGIO ITALIA, ITALIA AL CENTRO)-MAIE-CENTRO POPOLARE":
        "Noi Moderati - MAIE - Centro Popolare",
    "CIVICI D'ITALIA-NOI MODERATI (UDC-CORAGGIO ITALIA-NOI CON L'ITALIA-ITALIA AL CENTRO)-MAIE":
        "Noi Moderati - MAIE - Centro Popolare",
    "NOI MODERATI-MAIE": "Noi Moderati - MAIE - Centro Popolare",
    "MOVIMENTO 5 STELLE": "Movimento 5 Stelle",
    "ALLEANZA VERDI E SINISTRA": "Alleanza Verdi e Sinistra",
    "AZIONE-RENEW EUROPE": "Azione - Popolari Europeisti Riformatori - Renew Europe",
    "AZIONE-ITALIA VIVA-RENEW EUROPE": "Azione - Popolari Europeisti Riformatori - Renew Europe",
}
# componenti del Misto del Senato come le scrive il resoconto («Misto-AVS»): finché l'anagrafica del Senato non ha le
# componenti, la componente si legge dal gruppo dichiarato nell'intervento
_SIGLE_MISTO_SENATO = {
    "AVS": "Alleanza Verdi e Sinistra",
    "AZ-RE": "Azione - Popolari Europeisti Riformatori - Renew Europe",
    "AZ": "Azione - Popolari Europeisti Riformatori - Renew Europe",
    "AVANTI PSI": "Avanti PSI",
}


def partito(nome: str | None) -> str:
    """Il partito di un gruppo o di una componente del Misto, dal suo nome (della Camera o del Senato)."""
    if not nome:
        return NOME_MISTO
    return _STESSO_PARTITO.get(chiave(nome), nome)


def componente_senato(as_group: str | None) -> tuple[str | None, str | None]:
    """(componente, partito) dal gruppo dichiarato in un intervento del Misto del Senato («Misto-AVS»), o (None, None)."""
    m = re.match(r"\s*misto\s*[-–]\s*(.+)$", as_group or "", re.IGNORECASE)
    if not m:
        return None, None
    sigla = m.group(1).strip()
    return sigla, _SIGLE_MISTO_SENATO.get(chiave(sigla), f"Misto - {sigla}")


def e_misto(nome: str | None) -> bool:
    return chiave(nome) == "MISTO"


# gruppi della legislatura con almeno un membro, e componenti del Misto con membri oggi
SQL_GRUPPI = """
SELECT g.uri, g.chamber, g.kind, g.name, g.short_name, g.part_of
FROM grp g
WHERE g.legislature = %(leg)s AND g.chamber = ANY(%(rami)s)
  AND CASE WHEN g.kind = 'misto_component'
           THEN EXISTS (SELECT 1 FROM membership m WHERE m.grp = g.uri AND m.end_date IS NULL)
           ELSE EXISTS (SELECT 1 FROM membership m WHERE m.grp = g.uri) END
ORDER BY g.chamber, g.kind, g.name
"""


_CACHE: dict[tuple, tuple[float, dict]] = {}
_LUCCHETTO = threading.Lock()


def partiti_attesi(c: psycopg.Connection, rami: list[str]) -> dict[str, dict]:
    """I partiti attesi in una risposta sui rami dati: {partito: {"lato", "schieramento", "rami", "gruppi"}}. `lato` è
    il blocco del fascicolo (misto per il Misto e le componenti a sé), `schieramento` la regola di maggioranza.py. Il
    Misto c'è per chi non è in nessuna componente."""
    chiave_c = tuple(sorted(rami))
    with _LUCCHETTO:
        x = _CACHE.get(chiave_c)
        if x and time.monotonic() - x[0] < DURATA:
            return {k: dict(v) for k, v in x[1].items()}
    out = _carica(c, list(chiave_c))
    with _LUCCHETTO:
        _CACHE[chiave_c] = (time.monotonic(), out)
    return {k: dict(v) for k, v in out.items()}


def _carica(c: psycopg.Connection, rami: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    blocco: dict[str, bool] = {}
    for r in c.execute(SQL_GRUPPI, {"leg": LEGISLATURA, "rami": list(rami)}):
        nome = partito(r["name"])
        voce = out.setdefault(nome, {"rami": set(), "gruppi": []})
        # il Misto e le componenti che sono un partito a sé (in nessun ramo un gruppo) stanno nel blocco del Misto
        blocco[nome] = blocco.get(nome, True) and (e_misto(r["name"]) or r["kind"] == "misto_component")
        voce["rami"].add(r["chamber"])
        voce["gruppi"].append(r["uri"])
    sch = maggioranza.schieramenti(c)
    for nome, v in out.items():
        v["rami"] = sorted(v["rami"])
        v["schieramento"] = sch.lato(v["gruppi"])
        v["lato"] = MISTO if blocco[nome] else v["schieramento"]
    return out


def lato_di(nome_partito: str | None, attesi: dict[str, dict]) -> str:
    """Il lato di un partito; un partito che non è fra gli attesi è all'opposizione, una componente del Misto nel misto."""
    if not nome_partito:
        return OPPOSIZIONE
    if nome_partito == NOME_GOVERNO:
        return GOVERNO
    if nome_partito in attesi:
        return attesi[nome_partito]["lato"]
    if nome_partito.startswith("Misto - ") or e_misto(nome_partito):
        return MISTO
    return OPPOSIZIONE
