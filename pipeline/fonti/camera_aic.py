"""Sindacato ispettivo e indirizzo della Camera da dati.camera.it: interrogazioni (scritte, orali, in commissione),
interpellanze, mozioni, risoluzioni, ordini del giorno. Con il testo, i firmatari, il ministero destinatario,
i temi EuroVoc, le date di presentazione e di chiusura.

Circa 41 mila atti nella XIX: il lago li tiene per mese di presentazione (`leg19-aic-202507`). Ogni notte un indice
leggero (atto, ultima modifica) dice quali mesi sono cambiati, e si riscaricano solo quelli. aic.camera.it vieta
i robot (robots.txt): si usa solo SPARQL.
"""

from __future__ import annotations

import gzip
import json

from ..lago import Lago, controlla_calo
from .camera_ocd import ENDPOINT, PREFISSI, leg_uri
from .sparql import per_chiave

NOME = "camera_aic"
P = PREFISSI + "PREFIX ods:<http://lod.xdams.org/ontologies/ods/>\n"
BASE = """?aic a ocd:aic ; ocd:rif_leg <{LEG}> ; ocd:ramo "{RAMO}" ; ocd:startDate ?inizio ."""
RAMI = {"camera_aic": "Camera dei Deputati", "senato_aic": "Senato della Repubblica"}   # dati.camera.it ha anche gli atti del Senato

INDICE = """SELECT ?aic ?inizio ?modificato WHERE { """ + BASE + """ OPTIONAL { ?aic ods:modified ?modificato } {FILTRO} } ORDER BY ?aic"""
MESE = {
    "atti": """SELECT DISTINCT ?aic ?numero ?tipo ?titolo ?testo ?inizio ?fine ?concluso ?url WHERE { """ + BASE + """
 FILTER (STRSTARTS(STR(?inizio), "{MESE}")) ?aic dc:identifier ?numero ; dc:type ?tipo .
 OPTIONAL { ?aic dc:title ?titolo } OPTIONAL { ?aic dc:description ?testo } OPTIONAL { ?aic ocd:endDate ?fine }
 OPTIONAL { ?aic ocd:concluso ?concluso } OPTIONAL { ?aic dc:relation ?url } {FILTRO} } ORDER BY ?aic""",
    "firmatari": """SELECT DISTINCT ?aic ?deputato ?primo WHERE { """ + BASE + """ FILTER (STRSTARTS(STR(?inizio), "{MESE}"))
 { ?aic ocd:primo_firmatario ?deputato BIND("1" AS ?primo) } UNION { ?aic ocd:altro_firmatario ?deputato BIND("0" AS ?primo) } {FILTRO} } ORDER BY ?aic""",
    "destinatari": """SELECT DISTINCT ?aic ?destinatario WHERE { """ + BASE + """ FILTER (STRSTARTS(STR(?inizio), "{MESE}"))
 ?aic ocd:destinatario ?destinatario {FILTRO} } ORDER BY ?aic""",
    "temi": """SELECT DISTINCT ?aic ?tema WHERE { """ + BASE + """ FILTER (STRSTARTS(STR(?inizio), "{MESE}"))
 ?aic dcterms:subject ?tema {FILTRO} } ORDER BY ?aic""",
}


def chiave(mese: str, leg: int) -> str:
    return f"leg{leg}-aic-{mese}"


def scarica_senato(ctx) -> dict:
    """Gli stessi atti per il Senato, sempre da dati.camera.it (non tocca senato.it)."""
    return scarica(ctx, "senato_aic")


def _comprimi(dati) -> bytes:
    return gzip.compress(json.dumps(dati, ensure_ascii=False, sort_keys=True).encode("utf-8"), mtime=0)


def leggi(corpo: bytes):
    return json.loads(gzip.decompress(corpo))


def scarica(ctx, nome: str = NOME) -> dict:
    cfg = ctx.config["fonti"][nome]
    ramo = RAMI[nome]
    leg, pausa, massimo = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 0.5)), int(cfg.get("massimo_mesi_per_giro", 60))
    lago = Lago(ctx.cartella)
    k_indice = f"leg{leg}-aic-indice"
    prima = lago.ultimo(nome, k_indice)
    vecchio = {r["aic"]: r for r in leggi(lago.leggi(prima["file"]))} if prima else {}
    indice = per_chiave(ENDPOINT, P + INDICE.replace("{LEG}", leg_uri(leg)).replace("{RAMO}", ramo), "aic", pausa=pausa)
    # una riga per atto: le triple ripetute su più grafi danno righe doppie; si tiene l'ultima modifica
    unico: dict[str, dict] = {}
    for r in indice:
        if r["aic"] not in unico or r.get("modificato", "") > unico[r["aic"]].get("modificato", ""):
            unico[r["aic"]] = r
    indice = [unico[k] for k in sorted(unico)]
    if not indice:
        raise RuntimeError("indice degli atti di sindacato ispettivo vuoto")
    # l'indice dice quali atti ci sono: un calo forte è l'endpoint a metà, e i mesi riscaricati perderebbero atti
    controlla_calo(lago, nome, k_indice, len(indice), conta=lambda b: len(leggi(b)), massimo=float(cfg.get("calo_massimo", 0.05)))
    presenti = set(lago.chiavi(nome))
    mesi = sorted({r["inizio"][:6] for r in indice})
    cambiati = {r["inizio"][:6] for r in indice if vecchio.get(r["aic"]) != r} if vecchio else set()
    da_fare = [m for m in reversed(mesi) if chiave(m, leg) not in presenti or m in cambiati][:massimo]
    nuovi = 0
    for m in da_fare:
        dati = {nome: per_chiave(ENDPOINT, P + q.replace("{LEG}", leg_uri(leg)).replace("{RAMO}", ramo).replace("{MESE}", m), "aic", pagina=3000, pausa=pausa)
                for nome, q in MESE.items()}
        attesi = len({r["aic"] for r in indice if r["inizio"].startswith(m)})   # le triple sono ripetute su più grafi
        if len({r["aic"] for r in dati["atti"]}) != attesi:
            raise RuntimeError(f"mese {m}: {len({r['aic'] for r in dati['atti']})} atti scaricati, {attesi} nell'indice")
        nuovi += lago.salva(nome, chiave(m, leg), _comprimi(dati), ENDPOINT, "json.gz")["nuovo"]
    if len(da_fare) == len([m for m in mesi if chiave(m, leg) not in presenti or m in cambiati]):
        lago.salva(nome, k_indice, _comprimi(indice), ENDPOINT, "json.gz")  # l'indice solo a giro completo
    ctx.log(f"{nome}: {len(indice)} atti in {len(mesi)} mesi; {len(da_fare)} mesi riscaricati ({nuovi} cambiati)")
    return {"atti": len(indice), "mesi": len(mesi), "riscaricati": len(da_fare), "cambiati": nuovi}
