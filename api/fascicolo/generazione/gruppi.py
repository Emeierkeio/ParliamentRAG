"""I gruppi del fascicolo e la loro parte. Nomi, rami e lato vengono dal recupero (recupero_gruppi.partiti_attesi): un
partito ha lo stesso nome nei due rami, le componenti del Misto (+Europa, Futuro Nazionale…) sono partiti del blocco
Misto, mai «il Misto» intero. La parte di un partito è quella del recupero, cioè la regola unica di maggioranza.py; il
Misto e le sue componenti a sé hanno un blocco loro. Elenco in memoria per sei ore; i test ne fissano uno con
`imposta`."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass

from .. import recupero_gruppi as rg

log = logging.getLogger("parliamentrag.fascicolo")

DURATA = 6 * 3600
MISTO = rg.NOME_MISTO
MAGGIORANZA, OPPOSIZIONE, MISTO_PARTE = rg.MAGGIORANZA, rg.OPPOSIZIONE, rg.MISTO


def nome_partito(grezzo: str | None) -> str:
    """Il nome di un gruppo o di una componente (della Camera o del Senato) → il partito del fascicolo."""
    return rg.partito(grezzo)


@dataclass(frozen=True)
class Gruppo:
    nome: str
    parte: str                                   # maggioranza | opposizione | misto
    rami: frozenset[str] = frozenset({"camera"})
    componente: bool = False                     # una componente del Misto che è un partito a sé (+Europa…)


def carica(c, rami_: Iterable[str] = ("camera", "senato")) -> list[Gruppo]:
    """I partiti attesi e la loro parte, dai dati."""
    return [Gruppo(nome, v["lato"], frozenset(v["rami"]), v["lato"] == MISTO_PARTE and nome != MISTO)
            for nome, v in rg.partiti_attesi(c, list(rami_)).items()]


_blocco = threading.Lock()
_elenco: list[Gruppo] | None = None
_letto = 0.0
_fisso = False


def elenco() -> list[Gruppo]:
    """I gruppi di Camera e Senato, dalla memoria o dai dati. Se il database non risponde resta l'ultimo letto."""
    global _elenco, _letto
    with _blocco:
        if _elenco is not None and (_fisso or time.monotonic() - _letto < DURATA):
            return list(_elenco)
    try:
        from ...db import connessione
        with connessione() as c:
            nuovo = carica(c)
    except Exception as e:                          # noqa: BLE001
        log.error("gruppi non leggibili: %s", type(e).__name__)
        return list(_elenco or [])
    with _blocco:
        _elenco, _letto = nuovo, time.monotonic()
    return list(nuovo)


def imposta(gruppi: list[Gruppo]) -> None:
    """Fissa l'elenco (test). Con [] torna a leggerlo dai dati."""
    global _elenco, _fisso, _letto
    with _blocco:
        _elenco, _fisso, _letto = (list(gruppi) or None), bool(gruppi), time.monotonic()


def nomi(rami_: Iterable[str] | None = None) -> list[str]:
    """I partiti che il fascicolo si aspetta, per i rami della domanda (tutti con None)."""
    voluti = set(rami_) if rami_ is not None else None
    return [g.nome for g in elenco() if voluti is None or g.rami & voluti]


def coalizioni() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {MAGGIORANZA: [], OPPOSIZIONE: [], MISTO_PARTE: []}
    for g in elenco():
        out[g.parte].append(g.nome)
    return out


def parte(nome: str | None) -> str:
    """maggioranza, opposizione o misto; un nome che non si conosce conta come opposizione."""
    if not nome:
        return OPPOSIZIONE
    if nome.upper() == "GOVERNO":
        return MAGGIORANZA
    k = rg.chiave(nome_partito(nome))
    for g in elenco():
        if rg.chiave(g.nome) == k:
            return g.parte
    if rg.e_misto(nome) or nome.startswith("Misto - "):
        return MISTO_PARTE
    return OPPOSIZIONE


def e_componente(nome: str) -> bool:
    """Vero per una componente del Misto che è un partito a sé (+Europa…)."""
    k = rg.chiave(nome)
    return any(rg.chiave(g.nome) == k and g.componente for g in elenco())
