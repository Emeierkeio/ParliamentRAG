"""Disegni di legge del Senato da dati.senato.it (osr:Ddl): una riga per fase (S. 1468, S. 1468-B, con lo stesso
idDdl), titolo, natura, stato, presentazione, legge che ne è nata; firmatari senatori; presentatori che non sono
senatori (governo, deputati, regioni, CNEL, iniziativa popolare).

Circa 2 mila ddl: si rifà tutto ogni notte con poche richieste (i firmatari a intervalli di numero, per restare
sotto le 10 mila righe che l'endpoint restituisce al massimo). Si tengono solo le fasi del Senato (ramo S): il
Senato registra anche le fasi alla Camera, con numeri che si sovrappongono.
"""

from __future__ import annotations

import json
import re
import time

from ..lago import Lago
from .sparql import _richiesta

NOME = "senato_ddl"
ENDPOINT = "https://dati.senato.it/sparql"
P = "PREFIX osr:<http://dati.senato.it/osr/> PREFIX xsd:<http://www.w3.org/2001/XMLSchema#> "
DDL = P + """SELECT ?ddl ?idDdl ?numero ?titolo ?data ?natura ?stato ?ramo ?iniziativa ?legge ?dataLegge WHERE {
 ?ddl a osr:Ddl ; osr:legislatura {LEG} ; osr:idDdl ?idDdl ; osr:numeroFase ?numero ; osr:ramo ?ramo . FILTER(str(?ramo) = "S")
 OPTIONAL { ?ddl osr:titolo ?titolo } OPTIONAL { ?ddl osr:dataPresentazione ?data } OPTIONAL { ?ddl osr:natura ?natura }
 OPTIONAL { ?ddl osr:statoDdl ?stato } OPTIONAL { ?ddl osr:descrIniziativa ?iniziativa }
 OPTIONAL { ?ddl osr:numeroLegge ?legge } OPTIONAL { ?ddl osr:dataLegge ?dataLegge } } LIMIT 10000"""
FIRMATARI = P + """SELECT ?ddl ?senatore ?primo WHERE {
 ?ddl a osr:Ddl ; osr:legislatura {LEG} ; osr:numeroFase ?numero ; osr:ramo ?ramo ; osr:iniziativa ?i . FILTER(str(?ramo) = "S")
 ?i osr:senatore ?senatore . OPTIONAL { ?i osr:primoFirmatario ?primo }
 FILTER(xsd:integer(?numero) >= {DA} && xsd:integer(?numero) < {A}) } LIMIT 10000"""
PRESENTATORI = P + """SELECT ?ddl ?presentatore ?tipo ?deputato ?primo WHERE {
 ?ddl a osr:Ddl ; osr:legislatura {LEG} ; osr:ramo ?r ; osr:iniziativa ?i . FILTER(str(?r) = "S")
 ?i osr:tipoIniziativa ?tipo ; osr:presentatore ?presentatore . OPTIONAL { ?i osr:senatore ?sen } FILTER(!bound(?sen))
 OPTIONAL { ?i <http://dati.camera.it/ocd/rif_deputato> ?deputato } OPTIONAL { ?i osr:primoFirmatario ?primo } } LIMIT 10000"""
PASSO = 400


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 5))
    lago = Lago(ctx.cartella)
    ddl = _richiesta(ENDPOINT, DDL.replace("{LEG}", str(leg)), 2)
    time.sleep(pausa)
    if not ddl or len(ddl) >= 10000:
        raise RuntimeError(f"elenco dei ddl vuoto o tagliato ({len(ddl)} righe)")
    # il numero di fase può essere composto («13-14-B»): conta solo il primo numero
    massimo = max(int(re.match(r"\d+", r["numero"]).group()) for r in ddl if re.match(r"\d+", r["numero"]))
    if massimo > 20000:
        raise RuntimeError(f"numero di ddl inatteso ({massimo}): mi fermo prima di fare troppe richieste")
    firmatari, intervalli = [], [(da, da + PASSO) for da in range(0, massimo + 1, PASSO)]
    while intervalli:
        da, a = intervalli.pop(0)
        righe = _richiesta(ENDPOINT, FIRMATARI.replace("{LEG}", str(leg)).replace("{DA}", str(da)).replace("{A}", str(a)), 2)
        time.sleep(pausa)
        if len(righe) >= 10000 and a - da > 1:
            intervalli[:0] = [(da, (da + a) // 2), ((da + a) // 2, a)]
            continue
        firmatari += righe
    presentatori = _richiesta(ENDPOINT, PRESENTATORI.replace("{LEG}", str(leg)), 2)
    esito = {}
    for nome, righe in (("ddl", ddl), ("firmatari", firmatari), ("presentatori", presentatori)):
        righe.sort(key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
        esito[nome] = lago.salva(NOME, f"leg{leg}-{nome}", json.dumps(righe, ensure_ascii=False, indent=0).encode(), ENDPOINT, "json")["nuovo"]
    ctx.log(f"{NOME}: {len({r['ddl'] for r in ddl})} ddl, {len(firmatari)} firme, {len(presentatori)} presentatori")
    return {"ddl": len({r["ddl"] for r in ddl}), "firme": len(firmatari), "presentatori": len(presentatori)}
