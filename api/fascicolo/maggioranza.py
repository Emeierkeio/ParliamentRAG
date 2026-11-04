"""La regola della maggioranza, una per tutto il servizio (recupero, autorevolezza, generazione del fascicolo).

Un gruppo, o una componente del Misto, è di maggioranza a una data se nei voti di fiducia dei dodici mesi prima più
della metà dei suoi membri presenti (favorevoli, contrari, astenuti) ha votato a favore; altrimenti è all'opposizione.
Il gruppo di chi vota è quello alla data del voto, con la componente del Misto prima del Misto (group_at). Senza fiducie
nei dodici mesi vale la riserva: maggioranza se un membro, mentre era nel gruppo, ha avuto per più di GIORNI_MINIMI un
incarico nel governo in carica. Il Misto, cioè chi non sta in nessuna componente, non è un soggetto politico: resta
«misto».

Più gruppi con lo stesso nome nei due rami (un partito) si contano insieme: si sommano favorevoli e presenti.
I dati restano in memoria per DURATA secondi; `imposta` ne fissa altri (test)."""

from __future__ import annotations

import datetime as dt
import re
import threading
import time
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

import psycopg

LEGISLATURA = 19
MAGGIORANZA, OPPOSIZIONE, MISTO, GOVERNO = "maggioranza", "opposizione", "misto", "governo"
FINESTRA = 365                       # giorni di fiducie che contano
# le sovrapposizioni brevi sono passaggi di consegne, non sostegno: i ministri uscenti del governo Draghi hanno tenuto
# l'incarico per qualche giorno dopo l'ingresso nei gruppi della XIX
GIORNI_MINIMI = 30
DURATA = 6 * 3600

# il voto di ogni membro presente nelle questioni di fiducia, per gruppo alla data del voto (la componente del Misto prima
# del Misto, se no il gruppo che il voto attribuisce)
SQL_FIDUCIE = """
SELECT v.date, coalesce(group_at(b.person, v.date), b.grp) AS grp,
       count(*) FILTER (WHERE b.result = 'favor') AS fav,
       count(*) FILTER (WHERE b.result IN ('favor', 'against', 'abstain')) AS pres
FROM vote v JOIN ballot b ON b.vote = v.uri
WHERE v.confidence AND v.legislature = %(leg)s GROUP BY 1, 2"""

# riserva: gruppi e componenti con un membro che ha avuto un incarico nel governo in carica (anche con l'altra scheda,
# person_same_as) per più di GIORNI_MINIMI mentre era nel gruppo
SQL_AL_GOVERNO = """
WITH gov AS (SELECT uri FROM government WHERE start_date <= current_date AND (end_date IS NULL OR end_date > current_date)
             ORDER BY start_date DESC LIMIT 1),
     uff AS (SELECT o.person, o.start_date, o.end_date FROM office o, gov WHERE o.target = gov.uri OR o.target LIKE gov.uri || ':%%'),
     schede AS (SELECT person AS a, same_as AS b FROM person_same_as UNION SELECT same_as, person FROM person_same_as)
SELECT DISTINCT m.grp FROM membership m JOIN grp g ON g.uri = m.grp AND g.legislature = %(leg)s
JOIN uff u ON u.person = m.person OR u.person IN (SELECT b FROM schede WHERE a = m.person)
WHERE least(coalesce(m.end_date, '2100-01-01'), coalesce(u.end_date, '2100-01-01'))
      - greatest(coalesce(m.start_date, '1900-01-01'), u.start_date) > %(giorni)s"""


def _e_misto(nome: str | None) -> bool:
    t = unicodedata.normalize("NFKD", nome or "")
    return re.sub(r"\s+", " ", t).strip().upper() == "MISTO"


def lato_alla_data(fiducie: Iterable[tuple], il: dt.date, riserva: str, misto: bool = False) -> str:
    """La regola su un elenco di (data, favorevoli, presenti): maggioranza se nelle fiducie dei dodici mesi prima di `il`
    (estremo incluso) i favorevoli sono più della metà dei presenti, opposizione se no; senza fiducie nel periodo vale
    `riserva`. `misto`: il Misto senza componente, che resta misto."""
    if misto:
        return MISTO
    da = il - dt.timedelta(days=FINESTRA)
    favorevoli = presenti = 0
    for quando, f, p in fiducie:
        if da < quando <= il:
            favorevoli, presenti = favorevoli + f, presenti + p
    if not presenti:
        return riserva
    return MAGGIORANZA if favorevoli * 2 > presenti else OPPOSIZIONE


@dataclass
class Schieramenti:
    """Fiducie e riserva per gruppo (uri del gruppo o della componente), con i nomi per riconoscere il Misto."""
    fiducie: dict[str, list[tuple]]                  # uri -> [(data, favorevoli, presenti)]
    al_governo: set[str]                             # uri con la riserva «maggioranza»
    nomi: dict[str, str]                             # uri -> nome del gruppo
    caricati: float = field(default_factory=time.monotonic)
    _memo: dict = field(default_factory=dict)

    def lato(self, gruppi: str | Iterable[str] | None, il: dt.date | None = None) -> str:
        """Il lato di un gruppo, o di più gruppi dello stesso partito contati insieme, alla data (oggi se manca).
        Un gruppo che non si conosce è all'opposizione."""
        uris = (gruppi,) if isinstance(gruppi, str) or gruppi is None else tuple(sorted(set(gruppi)))
        uris = tuple(u for u in uris if u)
        if not uris:
            return OPPOSIZIONE
        il = il or dt.date.today()
        k = (uris, il)
        if k not in self._memo:
            if all(_e_misto(self.nomi.get(u)) for u in uris):
                self._memo[k] = MISTO
            else:
                validi = [u for u in uris if not _e_misto(self.nomi.get(u))]
                riserva = MAGGIORANZA if any(u in self.al_governo for u in validi) else OPPOSIZIONE
                self._memo[k] = lato_alla_data([f for u in validi for f in self.fiducie.get(u, [])], il, riserva)
        return self._memo[k]


def carica(c: psycopg.Connection) -> Schieramenti:
    """Fiducie, riserva e nomi dei gruppi della legislatura dal database."""
    fiducie: dict[str, list[tuple]] = {}
    for r in c.execute(SQL_FIDUCIE, {"leg": LEGISLATURA}):
        if r["grp"]:
            fiducie.setdefault(r["grp"], []).append((r["date"], r["fav"], r["pres"]))
    al_governo = {r["grp"] for r in c.execute(SQL_AL_GOVERNO, {"leg": LEGISLATURA, "giorni": GIORNI_MINIMI})}
    nomi = {r["uri"]: r["name"] for r in c.execute("SELECT uri, name FROM grp WHERE legislature = %s", (LEGISLATURA,))}
    return Schieramenti(fiducie, al_governo, nomi)


_blocco = threading.Lock()
_dati: Schieramenti | None = None
_fisso = False


def schieramenti(c: psycopg.Connection) -> Schieramenti:
    """Gli schieramenti in memoria; dopo DURATA secondi si rileggono."""
    global _dati
    with _blocco:
        d = _dati
        if d and (_fisso or time.monotonic() - d.caricati < DURATA):
            return d
    nuovi = carica(c)
    with _blocco:
        if not _fisso:
            _dati = nuovi
        return _dati or nuovi


def imposta(s: Schieramenti | None) -> None:
    """Fissa gli schieramenti (test); None torna a leggerli dal database."""
    global _dati, _fisso
    with _blocco:
        _dati, _fisso = s, s is not None


def lato(c: psycopg.Connection, gruppi: str | Iterable[str] | None, il: dt.date | None = None) -> str:
    """Scorciatoia: il lato di uno o più gruppi alla data."""
    return schieramenti(c).lato(gruppi, il)
