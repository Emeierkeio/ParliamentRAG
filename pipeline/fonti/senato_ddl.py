"""Disegni di legge del Senato da dati.senato.it (osr:Ddl): una riga per fase (S. 1468, S. 1468-B, con lo stesso
idDdl), titolo, natura, stato, presentazione, legge che ne è nata; firmatari senatori; presentatori che non sono
senatori (governo, deputati, regioni, CNEL, iniziativa popolare); assegnazioni alle commissioni (sede e data),
relatori con il senatore, data dell'ultimo stato e classificazione per materia (i termini TESEO dati al ddl intero).

Circa 2 mila ddl: si rifà tutto ogni notte con poche richieste (i firmatari a intervalli di numero, per restare
sotto le 10 mila righe che l'endpoint restituisce al massimo). Si tengono solo le fasi del Senato (ramo S): il
Senato registra anche le fasi alla Camera, con numeri che si sovrappongono.
"""

from __future__ import annotations

import json
import re
import time

from ..lago import Lago, controlla_calo
from .sparql import _richiesta

NOME = "senato_ddl"
ENDPOINT = "https://dati.senato.it/sparql"
P = "PREFIX osr:<http://dati.senato.it/osr/> PREFIX xsd:<http://www.w3.org/2001/XMLSchema#> "
DDL = P + """SELECT ?ddl ?idDdl ?numero ?titolo ?data ?natura ?stato ?dataStato ?ramo ?iniziativa ?legge ?dataLegge WHERE {
 ?ddl a osr:Ddl ; osr:legislatura {LEG} ; osr:idDdl ?idDdl ; osr:numeroFase ?numero ; osr:ramo ?ramo . FILTER(str(?ramo) = "S")
 OPTIONAL { ?ddl osr:titolo ?titolo } OPTIONAL { ?ddl osr:dataPresentazione ?data } OPTIONAL { ?ddl osr:natura ?natura }
 OPTIONAL { ?ddl osr:statoDdl ?stato } OPTIONAL { ?ddl osr:dataStatoDdl ?dataStato } OPTIONAL { ?ddl osr:descrIniziativa ?iniziativa }
 OPTIONAL { ?ddl osr:numeroLegge ?legge } OPTIONAL { ?ddl osr:dataLegge ?dataLegge } } LIMIT 10000"""
FIRMATARI = P + """SELECT ?ddl ?senatore ?primo WHERE {
 ?ddl a osr:Ddl ; osr:legislatura {LEG} ; osr:numeroFase ?numero ; osr:ramo ?ramo ; osr:iniziativa ?i . FILTER(str(?ramo) = "S")
 ?i osr:senatore ?senatore . OPTIONAL { ?i osr:primoFirmatario ?primo }
 FILTER(xsd:integer(?numero) >= {DA} && xsd:integer(?numero) < {A}) } LIMIT 10000"""
PRESENTATORI = P + """SELECT ?ddl ?presentatore ?tipo ?deputato ?primo WHERE {
 ?ddl a osr:Ddl ; osr:legislatura {LEG} ; osr:ramo ?r ; osr:iniziativa ?i . FILTER(str(?r) = "S")
 ?i osr:tipoIniziativa ?tipo ; osr:presentatore ?presentatore . OPTIONAL { ?i osr:senatore ?sen } FILTER(!bound(?sen))
 OPTIONAL { ?i <http://dati.camera.it/ocd/rif_deputato> ?deputato } OPTIONAL { ?i osr:primoFirmatario ?primo } } LIMIT 10000"""
ASSEGNAZIONI = P + """SELECT ?ddl ?etichetta ?tipo ?data ?organo ?sede WHERE {
 ?ddl a osr:Ddl ; osr:legislatura {LEG} ; osr:numeroFase ?numero ; osr:ramo ?ramo ; osr:assegnazione ?a . FILTER(str(?ramo) = "S")
 ?a osr:tipoCommissione ?tipo ; osr:dataAssegnazione ?data ; <http://www.w3.org/2000/01/rdf-schema#label> ?etichetta .
 OPTIONAL { ?a osr:organo ?organo } OPTIONAL { ?a osr:sede ?sede }
 FILTER(xsd:integer(?numero) >= {DA} && xsd:integer(?numero) < {A}) } LIMIT 10000"""
RELATORI = P + """SELECT ?ddl ?etichetta ?tipo ?minoranza ?data ?organo ?senatore WHERE {
 ?ddl a osr:Ddl ; osr:legislatura {LEG} ; osr:numeroFase ?numero ; osr:ramo ?ramo ; osr:relatore ?rel . FILTER(str(?ramo) = "S")
 ?rel <http://www.w3.org/2000/01/rdf-schema#label> ?etichetta . OPTIONAL { ?rel osr:tipoRelatore ?tipo }
 OPTIONAL { ?rel osr:diMinoranza ?minoranza } OPTIONAL { ?rel osr:dataNomina ?data } OPTIONAL { ?rel osr:organo ?organo }
 OPTIONAL { ?rel osr:senatore ?senatore }
 FILTER(xsd:integer(?numero) >= {DA} && xsd:integer(?numero) < {A}) } LIMIT 10000"""
# solo la classificazione del ddl intero («Generale»): quella per articolo è cinque volte tanto e dice di un comma, non dell'atto
CLASSIFICAZIONE = P + """SELECT DISTINCT ?ddl ?concetto WHERE {
 ?ddl a osr:Ddl ; osr:legislatura {LEG} ; osr:numeroFase ?numero ; osr:ramo ?ramo ; osr:classificazione ?c . FILTER(str(?ramo) = "S")
 ?c osr:livello ?livello ; <http://purl.org/dc/terms/subject> ?concetto . FILTER(str(?livello) = "Generale")
 FILTER(xsd:integer(?numero) >= {DA} && xsd:integer(?numero) < {A}) } LIMIT 10000"""
PASSO = 400


def _a_intervalli(query: str, leg: int, massimo: int, pausa: float) -> list[dict]:
    """Una query per intervallo di numeri dei ddl: l'endpoint dà al massimo 10 mila righe, un intervallo pieno si dimezza."""
    righe, intervalli = [], [(da, da + PASSO) for da in range(0, massimo + 1, PASSO)]
    while intervalli:
        da, a = intervalli.pop(0)
        parte = _richiesta(ENDPOINT, query.replace("{LEG}", str(leg)).replace("{DA}", str(da)).replace("{A}", str(a)), 2)
        time.sleep(pausa)
        if len(parte) >= 10000 and a - da > 1:
            intervalli[:0] = [(da, (da + a) // 2), ((da + a) // 2, a)]
            continue
        righe += parte
    return righe


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
    firmatari = _a_intervalli(FIRMATARI, leg, massimo, pausa)
    assegnazioni = _a_intervalli(ASSEGNAZIONI, leg, massimo, pausa)
    relatori = _a_intervalli(RELATORI, leg, massimo, pausa)
    classificazione = _a_intervalli(CLASSIFICAZIONE, leg, massimo, pausa)
    presentatori = _richiesta(ENDPOINT, PRESENTATORI.replace("{LEG}", str(leg)), 2)
    esito = {}
    tabelle = (("ddl", ddl), ("firmatari", firmatari), ("presentatori", presentatori), ("assegnazioni", assegnazioni),
               ("relatori", relatori), ("classificazione", classificazione))
    for nome, righe in tabelle:                          # sostituiscono intere tabelle: un calo forte è un errore dell'endpoint
        controlla_calo(lago, NOME, f"leg{leg}-{nome}", len(righe), massimo=float(cfg.get("calo_massimo", 0.05)))
    for nome, righe in tabelle:
        righe.sort(key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
        esito[nome] = lago.salva(NOME, f"leg{leg}-{nome}", json.dumps(righe, ensure_ascii=False, indent=0).encode(), ENDPOINT, "json")["nuovo"]
    ctx.log(f"{NOME}: {len({r['ddl'] for r in ddl})} ddl, {len(firmatari)} firme, {len(presentatori)} presentatori, "
            f"{len(assegnazioni)} assegnazioni, {len(relatori)} relatori, {len(classificazione)} termini di classificazione")
    return {"ddl": len({r["ddl"] for r in ddl}), "firme": len(firmatari), "presentatori": len(presentatori),
            "assegnazioni": len(assegnazioni), "relatori": len(relatori), "classificazione": len(classificazione)}
