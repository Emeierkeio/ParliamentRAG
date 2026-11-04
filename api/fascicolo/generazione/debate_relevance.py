"""Se il dibattito in cui è stato detto un passo riguarda il tema chiesto.

Un passo può essere vicino al tema e appartenere a un altro atto: sulla
riforma farmaceutica (S.1786) la ricerca ha portato il «ci asterremo» di
Fregolent, una dichiarazione di voto sulla legge di delegazione europea che
nomina l'industria farmaceutica. La citazione che fonda la posizione di un
gruppo deve venire da un dibattito sul tema (card 201, 19/10/2026).

Una chiamata al modello giudica i titoli dei dibattiti da cui vengono i passi:
  T  il dibattito è sul tema o su un atto che lo tratta
  G  il titolo non lo dice (question time, comunicazioni, più mozioni)
  A  il dibattito è su un altro atto o argomento, anche se tocca il tema
Senza risposta nessun dibattito viene giudicato e non cambia niente.

Prompt, modello e memoria sono quelli del recupero (recupero_modello.giudica_dibattiti): un giudizio solo, che il
recupero e la generazione condividono.
"""
from __future__ import annotations

from typing import Dict, Iterable

from .. import recupero_modello
from .contesto import IP

ON_TOPIC = recupero_modello.SUL_TEMA
GENERIC = recupero_modello.GENERICO
OTHER = recupero_modello.ALTRO

# ordine dei passi dentro un gruppo: prima i dibattiti sul tema, poi quelli
# non giudicati o generici, per ultimi gli altri atti
RANK = recupero_modello.ORDINE

MAX_TITLES = recupero_modello.TITOLI_MASSIMI
MODEL = recupero_modello.MODELLO_GIUDIZIO
PROMPT = recupero_modello.PROMPT_GIUDIZIO


def judge_debates(query: str, titles: Iterable[str]) -> Dict[str, str]:
    """Associa a ogni titolo di dibattito T, G o A per la domanda; {} se la chiamata fallisce. La spesa va sull'IP
    del fascicolo."""
    return recupero_modello.giudica_dibattiti(query, titles, IP.get())


def debate_rank(evidence: dict) -> int:
    """0 per un dibattito sul tema, 1 non giudicato o generico, 2 un altro atto."""
    return RANK.get(evidence.get("debate_relevance"), 1)
