"""Atti del Governo e proposte di nomina sottoposti al parere parlamentare, al Senato, da dati.senato.it
(osr:Documento): numero, titolo, data di presentazione, stato, chi lo presenta e il PDF del testo.

Gli open data non stanno dietro il WAF di senato.it. Sono circa 600 documenti: una query per tipo, ogni notte.
Le assegnazioni alle commissioni e i pareri non ci sono negli open data (stanno nelle schede di senato.it).
"""

from __future__ import annotations

import json
import time

from ..lago import Lago, controlla_calo
from .sparql import _richiesta

NOME = "senato_atti_governo"
ENDPOINT = "https://dati.senato.it/sparql"
TIPI = {"atti": "Atto del Governo sottoposto a parere parlamentare", "nomine": "Nomina sottoposta a parere parlamentare"}
QUERY = """PREFIX osr:<http://dati.senato.it/osr/>
SELECT ?doc ?numero ?titolo ?breve ?data ?stato ?url ?presentatore WHERE {
 ?doc a osr:Documento ; osr:legislatura {LEG} ; osr:tipoDoc ?tipo ; osr:numeroDoc ?numero . FILTER(str(?tipo) = "{TIPO}")
 OPTIONAL { ?doc osr:titolo ?titolo } OPTIONAL { ?doc osr:titoloBreve ?breve } OPTIONAL { ?doc osr:dataPresentazione ?data }
 OPTIONAL { ?doc osr:statoDoc ?stato } OPTIONAL { ?doc osr:URLTesto ?url }
 OPTIONAL { ?doc osr:iniziativa ?i . ?i osr:presentatore ?presentatore } } LIMIT 10000"""


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 5))
    lago, esito = Lago(ctx.cartella), {}
    tabelle = {}
    for nome, tipo in TIPI.items():
        righe = _richiesta(ENDPOINT, QUERY.replace("{LEG}", str(leg)).replace("{TIPO}", tipo), 2)
        time.sleep(pausa)
        if not righe or len(righe) >= 10000:
            raise RuntimeError(f"{nome}: elenco vuoto o tagliato ({len(righe)} righe)")
        tabelle[nome] = righe
    for nome, righe in tabelle.items():                  # sostituiscono intere tabelle: un calo forte è un errore dell'endpoint
        controlla_calo(lago, NOME, f"leg{leg}-{nome}", len(righe), massimo=float(cfg.get("calo_massimo", 0.05)))
    for nome, righe in tabelle.items():
        righe.sort(key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
        lago.salva(NOME, f"leg{leg}-{nome}", json.dumps(righe, ensure_ascii=False, indent=0).encode(), ENDPOINT, "json")
        esito[nome] = len({r["doc"] for r in righe})
    ctx.log(f"{NOME}: {esito['atti']} atti del Governo, {esito['nomine']} nomine")
    return esito
