"""Governi, ministeri e incarichi di governo da dati.camera.it: presidente, vicepresidenti, ministri, viceministri,
sottosegretari, con le date e il ministero. Anche le persone che non sono deputati (ministri senatori o tecnici).

Governi della legislatura e anche quelli ancora in carica al suo inizio (il governo Draghi presenta disegni di
legge nella XIX prima del giuramento del governo Meloni). Pochi dati: le query si rifanno ogni notte.
"""

from __future__ import annotations

from .camera_ocd import scarica_query

NOME = "camera_governo"

# i governi della legislatura, più quelli finiti dopo il suo inizio
GOVERNI = """{ ?governo a ocd:governo . { ?governo ocd:rif_leg <{LEG}> } UNION { ?governo ocd:endDate ?fine_g FILTER (STR(?fine_g) >= "{INIZIO}") } }"""

QUERY = {
    "governi": """SELECT DISTINCT ?governo ?titolo ?inizio ?fine WHERE {
 """ + GOVERNI + """ ?governo dc:title ?titolo . OPTIONAL { ?governo ocd:startDate ?inizio } OPTIONAL { ?governo ocd:endDate ?fine } }
 ORDER BY ?governo""",
    "ministeri": """SELECT DISTINCT ?organo ?governo ?nome ?dicastero WHERE {
 """ + GOVERNI + """ ?governo ocd:rif_membroGoverno ?m . ?m ocd:rif_organoGoverno ?organo . ?organo rdfs:label ?nome .
 OPTIONAL { ?organo ocd:dicastero ?dicastero } } ORDER BY ?organo""",
    "incarichi": """SELECT DISTINCT ?membro ?governo ?persona ?tipo ?carica ?nota ?organo ?interim ?inizio ?fine ?motivo WHERE {
 """ + GOVERNI + """ ?governo ocd:rif_membroGoverno ?membro .
 ?membro ocd:rif_persona ?persona ; ocd:membroGoverno ?tipo ; dc:title ?carica ; ocd:startDate ?inizio .
 OPTIONAL { ?membro ocd:rif_organoGoverno ?organo } OPTIONAL { ?membro dc:description ?nota } OPTIONAL { ?membro ocd:interim ?interim }
 OPTIONAL { ?membro ocd:endDate ?fine } OPTIONAL { ?membro ocd:motivoTermine ?motivo } } ORDER BY ?membro""",
    # anagrafica di chi è al governo: per chi è anche deputato la completa già camera_ocd
    "persone": """SELECT DISTINCT ?persona ?nome ?cognome ?genere ?foto ?nascita ?luogo ?descrizione WHERE {
 """ + GOVERNI + """ ?governo ocd:rif_membroGoverno ?membro . ?membro ocd:rif_persona ?persona .
 ?persona foaf:firstName ?nome ; foaf:surname ?cognome .
 OPTIONAL { ?persona foaf:gender ?genere } OPTIONAL { ?persona foaf:depiction ?foto } OPTIONAL { ?persona dc:description ?descrizione }
 OPTIONAL { ?persona bio:Birth ?b . ?b bio:date ?nascita . OPTIONAL { ?b rdfs:label ?luogo } } } ORDER BY ?persona""",
}


def scarica(ctx) -> dict:
    return scarica_query(ctx, NOME, QUERY)
