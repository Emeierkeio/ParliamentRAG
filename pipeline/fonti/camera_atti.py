"""Progetti di legge della Camera da dati.camera.it: atti, firmatari, iter, assegnazioni, relatori, abbinamenti,
trasmissioni al Senato e versioni del testo.

Sono circa 3 mila atti nella XIX: le query si rifanno tutte ogni notte (pochi secondi), come l'anagrafica.
Una query per file nel lago (`leg19-<nome>`); se la Camera non cambia niente il lago non riscrive niente.
"""

from __future__ import annotations

from .camera_ocd import scarica_query

NOME = "camera_atti"

QUERY = {
    "atti": """SELECT DISTINCT ?atto ?numero ?titolo ?tipo ?natura ?iniziativa ?data ?descrizione ?scheda ?testo WHERE {
 ?atto a ocd:atto ; ocd:rif_leg <{LEG}> ; dc:identifier ?numero .
 OPTIONAL { ?atto dc:title ?titolo } OPTIONAL { ?atto dc:type ?tipo } OPTIONAL { ?atto ocd:rif_natura ?natura } OPTIONAL { ?atto ocd:iniziativa ?iniziativa }
 OPTIONAL { ?atto dc:date ?data } OPTIONAL { ?atto dc:description ?descrizione } OPTIONAL { ?atto dcterms:isReferencedBy ?scheda }
 OPTIONAL { ?atto dc:relation ?testo } {FILTRO} } ORDER BY ?atto""",
    # i deputati sono uri; i membri del governo sono nodi anonimi con la persona e la carica (Ministro della Difesa)
    "firmatari": """SELECT DISTINCT ?atto ?firmatario ?primo ?carica WHERE {
 ?atto a ocd:atto ; ocd:rif_leg <{LEG}> .
 { ?atto ocd:primo_firmatario ?f BIND("1" AS ?primo) } UNION { ?atto ocd:altro_firmatario ?f BIND("0" AS ?primo) }
 OPTIONAL { ?f ocd:rif_persona ?persona } OPTIONAL { ?f ocd:ruolo ?carica } BIND(IF(isBlank(?f), ?persona, ?f) AS ?firmatario) {FILTRO} } ORDER BY ?atto""",
    "iter": """SELECT DISTINCT ?atto ?stato ?titolo ?data WHERE {
 ?atto a ocd:atto ; ocd:rif_leg <{LEG}> ; ocd:rif_statoIter ?stato . ?stato dc:title ?titolo . OPTIONAL { ?stato dc:date ?data } {FILTRO} } ORDER BY ?atto""",
    "assegnazioni": """SELECT DISTINCT ?atto ?assegnazione ?organo ?sede ?data ?titolo WHERE {
 ?atto a ocd:atto ; ocd:rif_leg <{LEG}> ; ocd:rif_assegnazione ?assegnazione . ?assegnazione ocd:rif_organo ?organo .
 OPTIONAL { ?assegnazione ocd:sede ?sede } OPTIONAL { ?assegnazione dc:date ?data } OPTIONAL { ?assegnazione dc:title ?titolo } {FILTRO} } ORDER BY ?atto""",
    "relatori": """SELECT DISTINCT ?atto ?relatore ?titolo ?tipo WHERE {
 ?atto a ocd:atto ; ocd:rif_leg <{LEG}> ; ocd:rif_relatore ?relatore . ?relatore dc:title ?titolo . OPTIONAL { ?relatore dc:type ?tipo } {FILTRO} } ORDER BY ?atto""",
    "abbinamenti": """SELECT DISTINCT ?atto ?portante ?tipo_testo WHERE {
 ?atto a ocd:atto ; ocd:rif_leg <{LEG}> ; ocd:rif_abbinamento ?ab . ?ab ocd:attoPortante ?portante . OPTIONAL { ?ab ocd:tipoTesto ?tipo_testo } {FILTRO} } ORDER BY ?atto""",
    "trasmissioni": """SELECT DISTINCT ?atto ?trasmissione ?titolo ?data ?provenienza WHERE {
 ?atto a ocd:atto ; ocd:rif_leg <{LEG}> ; ocd:rif_trasmissione ?trasmissione . ?trasmissione dc:title ?titolo .
 OPTIONAL { ?trasmissione dc:date ?data } OPTIONAL { ?trasmissione dcterms:provenance ?provenienza } {FILTRO} } ORDER BY ?atto""",
    "versioni": """SELECT DISTINCT ?atto ?versione ?titolo ?data ?url WHERE {
 ?atto a ocd:atto ; ocd:rif_leg <{LEG}> ; ocd:rif_versioneTestoAtto ?versione .
 OPTIONAL { ?versione dc:title ?titolo } OPTIONAL { ?versione dc:date ?data } OPTIONAL { ?versione dcterms:isReferencedBy ?url } {FILTRO} } ORDER BY ?atto""",
}


def scarica(ctx) -> dict:
    # paginazione per atto: con OFFSET l'endpoint dà errore 500 sulle query più grandi (iter, versioni)
    return scarica_query(ctx, NOME, QUERY, per="atto")
