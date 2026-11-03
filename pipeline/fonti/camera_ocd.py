"""Anagrafica della Camera da dati.camera.it (ontologia OCD): deputati, mandati, gruppi, componenti del Misto,
organi (commissioni, giunte, delegazioni), appartenenze e cariche, tutti con le loro date.

Ogni query finisce nel lago come un file JSON a sé (chiave `leg19-<nome>`): se la Camera non cambia niente,
il lago non riscrive niente. Le righe si ordinano prima di salvarle, così lo stesso contenuto dà la stessa impronta.
"""

from __future__ import annotations

import json
import time

from ..lago import Lago
from .sparql import interroga, per_chiave

NOME = "camera_ocd"
ENDPOINT = "https://dati.camera.it/sparql"
PREFISSI = """PREFIX ocd:<http://dati.camera.it/ocd/> PREFIX foaf:<http://xmlns.com/foaf/0.1/> PREFIX bio:<http://purl.org/vocab/bio/0.1/>
PREFIX dc:<http://purl.org/dc/elements/1.1/> PREFIX dcterms:<http://purl.org/dc/terms/> PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
"""

# {LEG} diventa l'uri della legislatura. Le variabili sono valori grezzi della fonte: le pulisce la trasformazione.
QUERY = {
    "persone": """SELECT DISTINCT ?persona ?nome ?cognome ?genere ?foto ?nascita ?luogo ?descrizione WHERE {
 ?persona a foaf:Person ; ocd:rif_mandatoCamera ?m ; foaf:firstName ?nome ; foaf:surname ?cognome . ?m ocd:rif_leg <{LEG}> .
 OPTIONAL { ?persona foaf:gender ?genere } OPTIONAL { ?persona foaf:depiction ?foto } OPTIONAL { ?persona dc:description ?descrizione }
 OPTIONAL { ?persona bio:Birth ?b . ?b bio:date ?nascita . OPTIONAL { ?b rdfs:label ?luogo } } } ORDER BY ?persona""",
    "mandati": """SELECT DISTINCT ?persona ?mandato ?inizio ?fine ?motivo ?convalida ?circoscrizione ?collegio ?sistema ?lista WHERE {
 ?persona a foaf:Person ; ocd:rif_mandatoCamera ?mandato . ?mandato ocd:rif_leg <{LEG}> ; ocd:startDate ?inizio .
 OPTIONAL { ?mandato ocd:endDate ?fine } OPTIONAL { ?mandato ocd:motivoTermine ?motivo } OPTIONAL { ?mandato ocd:convalida ?convalida }
 OPTIONAL { ?mandato ocd:rif_elezione ?e . OPTIONAL { ?e dc:coverage ?circoscrizione } OPTIONAL { ?e dcterms:spatial ?collegio }
   OPTIONAL { ?e ocd:tipoElezione ?sistema } OPTIONAL { ?e ocd:lista ?lista } } } ORDER BY ?mandato""",
    "gruppi": """SELECT DISTINCT ?gruppo ?titolo ?sigla ?inizio ?fine WHERE {
 ?gruppo a ocd:gruppoParlamentare ; ocd:rif_leg <{LEG}> ; dc:title ?titolo .
 OPTIONAL { ?gruppo dcterms:alternative ?sigla } OPTIONAL { ?gruppo ocd:startDate ?inizio } OPTIONAL { ?gruppo ocd:endDate ?fine } } ORDER BY ?gruppo""",
    "adesioni": """SELECT DISTINCT ?deputato ?gruppo ?inizio ?fine ?motivo WHERE {
 ?deputato a ocd:deputato ; ocd:rif_leg <{LEG}> ; ocd:aderisce ?a . ?a ocd:rif_gruppoParlamentare ?gruppo ; ocd:startDate ?inizio .
 OPTIONAL { ?a ocd:endDate ?fine } OPTIONAL { ?a ocd:motivoTermine ?motivo } } ORDER BY ?deputato ?inizio ?gruppo""",
    "componenti_misto": """SELECT DISTINCT ?componente ?titolo ?sigla ?cinizio ?cfine ?deputato ?inizio ?fine WHERE {
 ?componente a ocd:componenteGruppoMisto ; ocd:rif_leg <{LEG}> ; dc:title ?titolo ; ocd:siComponeDi ?a . ?a ocd:rif_deputato ?deputato .
 OPTIONAL { ?componente dcterms:alternative ?sigla } OPTIONAL { ?componente ocd:startDate ?cinizio } OPTIONAL { ?componente ocd:endDate ?cfine }
 OPTIONAL { ?a ocd:startDate ?inizio } OPTIONAL { ?a ocd:endDate ?fine } } ORDER BY ?componente ?deputato ?inizio""",
    "organi": """SELECT DISTINCT ?organo ?titolo ?tipo ?inizio ?fine ?parte WHERE {
 ?organo a ocd:organo ; ocd:rif_leg <{LEG}> ; dc:title ?titolo .
 OPTIONAL { ?organo dc:type ?tipo } OPTIONAL { ?organo ocd:startDate ?inizio } OPTIONAL { ?organo ocd:endDate ?fine }
 OPTIONAL { ?organo dcterms:isPartOf ?parte } } ORDER BY ?organo""",
    "membri_organi": """SELECT DISTINCT ?deputato ?organo ?tipo ?inizio ?fine ?motivo WHERE {
 ?deputato a ocd:deputato ; ocd:rif_leg <{LEG}> ; ocd:membro ?x . ?x ocd:rif_organo ?organo ; ocd:startDate ?inizio .
 OPTIONAL { ?x dc:type ?tipo } OPTIONAL { ?x ocd:endDate ?fine } OPTIONAL { ?x ocd:motivoTermine ?motivo } } ORDER BY ?deputato ?organo ?inizio""",
    "uffici": """SELECT DISTINCT ?deputato ?organo ?carica ?inizio ?fine WHERE {
 ?u a ocd:ufficioParlamentare ; ocd:rif_leg <{LEG}> ; ocd:rif_deputato ?deputato ; ocd:rif_organo ?organo ; ocd:carica ?carica ; ocd:startDate ?inizio .
 OPTIONAL { ?u ocd:endDate ?fine } } ORDER BY ?deputato ?organo ?carica ?inizio""",
    # i senatori della legislatura come li registra la Camera (id della Camera): servono alla corrispondenza con
    # dati.senato.it, che usa id suoi
    "senatori": """SELECT DISTINCT ?senatore ?persona ?nome ?cognome ?genere WHERE {
 ?senatore a ocd:senatore ; ocd:rif_leg <{LEG}> ; ocd:rif_mandatoSenato ?m . ?persona ocd:rif_mandatoSenato ?m ; a foaf:Person .
 OPTIONAL { ?persona foaf:firstName ?nome } OPTIONAL { ?persona foaf:surname ?cognome } OPTIONAL { ?persona foaf:gender ?genere } } ORDER BY ?senatore""",
    "incarichi_gruppo": """SELECT DISTINCT ?deputato ?gruppo ?ruolo ?inizio ?fine WHERE {
 ?i a ocd:incarico ; ocd:rif_leg <{LEG}> ; ocd:rif_deputato ?deputato ; ocd:rif_gruppoParlamentare ?gruppo ; ocd:ruolo ?ruolo ; ocd:startDate ?inizio .
 OPTIONAL { ?i ocd:endDate ?fine } } ORDER BY ?deputato ?gruppo ?ruolo ?inizio""",
}


def leg_uri(leg: int) -> str:
    return f"http://dati.camera.it/ocd/legislatura.rdf/repubblica_{leg}"


def chiave(nome: str, leg: int) -> str:
    return f"leg{leg}-{nome}"


def scarica(ctx) -> dict:
    return scarica_query(ctx, NOME, QUERY)


def scarica_query(ctx, fonte: str, query: dict[str, str], per: str | None = None, endpoint: str = ENDPOINT, prefissi: str = PREFISSI,
                  leg_uri_di=leg_uri) -> dict:
    """Esegue tutte le query di una fonte e le salva nel lago, una per file. La usano anche camera_atti e il Senato."""
    cfg = ctx.config["fonti"][fonte]
    leg = int(cfg["legislatura"])
    lago, esito = Lago(ctx.cartella), {}
    for nome, q in query.items():
        testo = prefissi + q.replace("{LEG}", leg_uri_di(leg)).replace("{INIZIO}", str(cfg.get("inizio_legislatura", "")))
        pausa = float(cfg.get("pausa_secondi", 0.5))
        righe = per_chiave(endpoint, testo, per, pausa=pausa) if per else interroga(endpoint, testo, pausa=pausa)
        time.sleep(pausa)
        if not righe:
            raise RuntimeError(f"{nome}: nessuna riga, l'endpoint della Camera potrebbe avere un problema")
        righe.sort(key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
        corpo = json.dumps(righe, ensure_ascii=False, indent=0).encode("utf-8")
        s = lago.salva(fonte, chiave(nome, leg), corpo, endpoint, "json")
        esito[nome] = {"righe": len(righe), "nuovo": s["nuovo"]}
    ctx.log(f"{fonte}: " + ", ".join(f"{k} {v['righe']}{'*' if v['nuovo'] else ''}" for k, v in esito.items()))
    return esito
