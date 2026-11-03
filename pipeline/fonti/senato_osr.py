"""Anagrafica del Senato da dati.senato.it (ontologia OSR, che riusa parte di OCD): senatori, mandati, gruppi con le
loro denominazioni nel tempo, adesioni ai gruppi, appartenenza alle commissioni.

dati.senato.it non è dietro al WAF di senato.it, ma ha limiti stretti:
niente BIND né VALUES, al massimo 10 mila righe contando l'OFFSET, URL lunghi rifiutati, e senato.it blocca l'IP
dopo circa 400 richieste ravvicinate. Qui sono poche query piccole, con una pausa lunga fra l'una e l'altra.
Le componenti del Misto non ci sono: stanno solo in una pagina di senato.it (dietro il WAF), da fare a parte.
"""

from __future__ import annotations

from .camera_ocd import scarica_query

NOME = "senato_osr"
ENDPOINT = "https://dati.senato.it/sparql"
PREFISSI = """PREFIX osr:<http://dati.senato.it/osr/> PREFIX ocd:<http://dati.camera.it/ocd/> PREFIX foaf:<http://xmlns.com/foaf/0.1/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
"""
# {LEG} qui è il numero della legislatura (osr:legislatura è un intero, non un uri).
# Il tipo ocd:mandatoSenato serve: dati.senato.it ha anche i mandati alla Camera di alcune persone (38 deputati nella XIX).
QUERY = {
    "persone": """SELECT DISTINCT ?senatore ?nome ?cognome ?etichetta ?genere ?foto ?professione WHERE {
 ?senatore a foaf:Person ; osr:mandato ?m . ?m a ocd:mandatoSenato ; osr:legislatura {LEG} . ?senatore rdfs:label ?etichetta .
 OPTIONAL { ?senatore foaf:firstName ?nome } OPTIONAL { ?senatore foaf:lastName ?cognome } OPTIONAL { ?senatore foaf:gender ?genere }
 OPTIONAL { ?senatore foaf:depiction ?foto } OPTIONAL { ?senatore osr:professione ?p . ?p rdfs:label ?professione } } ORDER BY ?senatore""",
    "mandati": """SELECT DISTINCT ?senatore ?mandato ?tipo ?inizio ?fine ?motivo ?collegio ?elezione ?regione WHERE {
 ?senatore osr:mandato ?mandato . ?mandato a ocd:mandatoSenato ; osr:legislatura {LEG} .
 OPTIONAL { ?mandato osr:tipoMandato ?tipo } OPTIONAL { ?mandato osr:inizio ?inizio } OPTIONAL { ?mandato osr:fine ?fine }
 OPTIONAL { ?mandato osr:tipoFineMandato ?motivo } OPTIONAL { ?mandato osr:collegioElezione ?collegio }
 OPTIONAL { ?mandato osr:tipoElezione ?elezione } OPTIONAL { ?mandato osr:regioneElezione ?regione } } ORDER BY ?senatore ?inizio""",
    "denominazioni": """SELECT DISTINCT ?gruppo ?titolo ?breve ?inizio ?fine WHERE {
 ?a osr:legislatura {LEG} ; osr:gruppo ?gruppo . ?gruppo osr:denominazione ?d .
 ?d osr:titolo ?titolo ; osr:inizio ?inizio . OPTIONAL { ?d osr:titoloBreve ?breve } OPTIONAL { ?d osr:fine ?fine } } ORDER BY ?gruppo ?inizio""",
    "adesioni": """SELECT DISTINCT ?senatore ?gruppo ?inizio ?fine ?carica WHERE {
 ?senatore ocd:aderisce ?a . ?a osr:legislatura {LEG} ; osr:gruppo ?gruppo ; osr:inizio ?inizio .
 OPTIONAL { ?a osr:fine ?fine } OPTIONAL { ?a osr:carica ?carica } } ORDER BY ?senatore ?inizio""",
    "commissioni": """SELECT DISTINCT ?senatore ?commissione ?inizio ?fine ?carica ?titolo ?materia ?dinizio ?dfine WHERE {
 ?senatore osr:afferisce ?af . ?af osr:legislatura {LEG} ; osr:commissione ?commissione .
 OPTIONAL { ?af osr:inizio ?inizio } OPTIONAL { ?af osr:fine ?fine } OPTIONAL { ?af osr:carica ?carica }
 OPTIONAL { ?commissione osr:denominazione ?d . ?d osr:titolo ?titolo ; osr:inizio ?dinizio .
            OPTIONAL { ?d osr:titoloBreve ?materia } OPTIONAL { ?d osr:fine ?dfine } } } ORDER BY ?senatore ?inizio""",
}


def scarica(ctx) -> dict:
    return scarica_query(ctx, NOME, QUERY, endpoint=ENDPOINT, prefissi=PREFISSI, leg_uri_di=str)
