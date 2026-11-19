"""Votazioni elettroniche dell'Assemblea della Camera da dati.camera.it: ogni votazione e il voto di ogni deputato.

Un file nel lago per seduta (`leg19-voti-sed0722`, JSON compresso): circa 13 mila voti per una seduta piena.
Per sapere quali sedute riscaricare, ogni giro legge un indice piccolo (votazioni per seduta e ultima modifica)
e lo confronta con quello del giro prima; in più ricontrolla le ultime sedute, che la Camera completa nei giorni dopo.

Gli open data arrivano il pomeriggio del giorno dopo la seduta. Le sedute che non ci sono ancora si leggono dal sito
(`camera_voti_sito`) e si salvano con la stessa chiave e `fonte: sito`: provvisorie, sostituite al primo giro in cui la
seduta compare negli open data.
"""

from __future__ import annotations

import gzip
import json
import re

from ..lago import Lago
from . import camera_voti_sito
from .camera_ocd import ENDPOINT, PREFISSI, leg_uri
from .sparql import interroga

NOME = "camera_voti"
PREFISSI_V = PREFISSI + "PREFIX ods:<http://lod.xdams.org/ontologies/ods/>\n"

INDICE = """SELECT ?seduta (COUNT(DISTINCT ?v) AS ?votazioni) (MAX(?m) AS ?modificata) WHERE {
 ?v a ocd:votazione ; ocd:rif_leg <{LEG}> ; ocd:rif_seduta ?seduta . OPTIONAL { ?v ods:modified ?m } } GROUP BY ?seduta ORDER BY ?seduta"""

# le votazioni si chiedono come triple e si ricompongono qui: la stessa richiesta con un OPTIONAL per campo
# va in timeout (504) su molte sedute, le triple tornano in un secondo
VOTAZIONI = """SELECT ?votazione ?p ?o WHERE { ?votazione a ocd:votazione ; ocd:rif_seduta <{SEDUTA}> ; ?p ?o }"""
CAMPI = {"http://purl.org/dc/elements/1.1/identifier": "numero", "http://purl.org/dc/elements/1.1/title": "titolo",
         "http://purl.org/dc/elements/1.1/description": "descrizione", "http://purl.org/dc/elements/1.1/type": "tipo",
         "http://purl.org/dc/elements/1.1/date": "data", "http://purl.org/dc/elements/1.1/relation": "scheda",
         "http://dati.camera.it/ocd/favorevoli": "favorevoli", "http://dati.camera.it/ocd/contrari": "contrari",
         "http://dati.camera.it/ocd/astenuti": "astenuti", "http://dati.camera.it/ocd/presenti": "presenti",
         "http://dati.camera.it/ocd/votanti": "votanti", "http://dati.camera.it/ocd/maggioranza": "maggioranza",
         "http://dati.camera.it/ocd/approvato": "approvato", "http://dati.camera.it/ocd/votazioneSegreta": "segreta",
         "http://dati.camera.it/ocd/votazioneFinale": "finale", "http://dati.camera.it/ocd/richiestaFiducia": "fiducia",
         "http://dati.camera.it/ocd/presiedutaDa": "presidente"}
MULTIPLI = {"http://dati.camera.it/ocd/rif_attoCamera": "atto", "http://dati.camera.it/ocd/rif_aic": "aic"}


def ricomponi(triple: list[dict]) -> list[dict]:
    """Dalle triple alle righe di prima: una riga per votazione, più una per ogni altro atto o atto di indirizzo votato."""
    base: dict[str, dict] = {}
    multi: dict[str, list] = {}
    for t in triple:
        v, p, o = t["votazione"], t["p"], t["o"]
        r = base.setdefault(v, {"votazione": v})
        if p in CAMPI:
            r.setdefault(CAMPI[p], o)
        elif p in MULTIPLI and (MULTIPLI[p], o) not in multi.setdefault(v, []):
            multi[v].append((MULTIPLI[p], o))
    righe = []
    for v in sorted(base):
        extra = sorted(multi.get(v, [])) or [None]
        righe += [{**base[v], **({k: o} if (k_o := e) and (k := k_o[0]) and (o := k_o[1]) else {})} for e in extra]
    return righe


# i voti si chiedono per blocchi di votazioni: l'endpoint restituisce al massimo 10 mila righe per risposta,
# una votazione ne ha al più 400 e una seduta ne può avere 30 mila. Niente ORDER BY: si ordina qui.
BLOCCO = 20
VOTI = """SELECT DISTINCT ?votazione ?deputato ?tipo ?nota ?gruppo ?componente WHERE {
 VALUES ?votazione { {VOTAZIONI} } ?voto a ocd:voto ; ocd:rif_votazione ?votazione ; ocd:rif_deputato ?deputato ; dc:type ?tipo .
 OPTIONAL { ?voto dc:description ?nota } OPTIONAL { ?voto ocd:rif_gruppoParlamentare ?gruppo } OPTIONAL { ?voto ocd:rif_componente ?componente } }"""
# il totale dei voti della seduta, per accorgersi di una risposta tagliata
CONTA_VOTI = """SELECT (COUNT(DISTINCT ?voto) AS ?n) WHERE { ?votazione ocd:rif_seduta <{SEDUTA}> . ?voto a ocd:voto ; ocd:rif_votazione ?votazione }"""


def numero_seduta(uri: str) -> int:
    return int(re.search(r"_(\d+)$", uri).group(1))


def chiave(numero: int, leg: int) -> str:
    return f"leg{leg}-voti-sed{numero:04d}"


def _comprimi(dati) -> bytes:
    # mtime=0: lo stesso contenuto dà gli stessi byte, quindi la stessa impronta nel lago
    return gzip.compress(json.dumps(dati, ensure_ascii=False, sort_keys=True).encode("utf-8"), mtime=0)


def leggi(corpo: bytes):
    return json.loads(gzip.decompress(corpo))


def _seduta(s: str, pausa: float) -> tuple[list, list]:
    """Votazioni e voti di una seduta, con il controllo del totale."""
    votazioni = ricomponi(interroga(ENDPOINT, PREFISSI_V + VOTAZIONI.replace("{SEDUTA}", s), pagina=10_000, pausa=pausa))
    elenco = sorted({v["votazione"] for v in votazioni})
    voti = []
    for i in range(0, len(elenco), BLOCCO):
        valori = " ".join(f"<{x}>" for x in elenco[i:i + BLOCCO])
        voti += interroga(ENDPOINT, PREFISSI_V + VOTI.replace("{VOTAZIONI}", valori), pagina=10_000, pausa=pausa)
    attesi = int(interroga(ENDPOINT, PREFISSI_V + CONTA_VOTI.replace("{SEDUTA}", s))[0]["n"])
    coppie = {(v["votazione"], v["deputato"]) for v in voti}
    if len(coppie) != attesi:
        raise RuntimeError(f"{s}: {len(coppie)} voti scaricati, {attesi} attesi: risposta incompleta")
    voti.sort(key=lambda v: (v["votazione"], v["deputato"], v.get("tipo", "")))
    return votazioni, voti


def _dal_sito(ctx, lago: Lago, leg: int, indice: list[dict], cfg: dict) -> dict:
    """Le sedute vicine all'ultima degli open data che lì non ci sono: si provano sul sito e, se hanno votazioni, si
    salvano come provvisorie. Un errore qui non ferma il passo: gli open data arrivano comunque il giorno dopo."""
    avanti, indietro = int(cfg.get("sito_sedute_avanti", 6)), int(cfg.get("sito_sedute_indietro", 6))
    if avanti <= 0:
        return {}
    negli_open_data = {numero_seduta(r["seduta"]) for r in indice}
    ultima = max(negli_open_data)
    anagrafica, riferimento = lago.ultimo("camera_ocd", f"leg{leg}-persone"), lago.ultimo(NOME, chiave(ultima, leg))
    if not anagrafica or not riferimento:
        return {"dal_sito": 0, "dal_sito_errori": ["manca l'anagrafica o l'ultima seduta degli open data"]}
    persone = json.loads(lago.leggi(anagrafica["file"]))
    gruppi = camera_voti_sito.gruppi_dai_voti(leggi(lago.leggi(riferimento["file"]))["voti"])
    presenti, salvate, errori = set(lago.chiavi(NOME)), [], []
    for n in range(max(1, ultima - indietro), ultima + avanti + 1):
        k = chiave(n, leg)
        if n in negli_open_data:
            continue
        if k in presenti and leggi(lago.leggi(lago.ultimo(NOME, k)["file"])).get("fonte") != "sito":
            continue                                  # una seduta degli open data uscita dall'indice: si tiene com'è
        try:
            schede = camera_voti_sito.schede_seduta(leg, n, pausa=float(cfg.get("sito_pausa_secondi", 1.0)))
            if schede:
                dati = camera_voti_sito.in_formato_ocd(schede, leg, persone, gruppi)
                lago.salva(NOME, k, _comprimi(dati), camera_voti_sito.SCHEDA.format(leg=camera_voti_sito.romano(leg), seduta=n, numero=1), "json.gz")
                salvate.append(n)
        except Exception as e:  # noqa: BLE001
            errori.append(f"{n}: {str(e)[:160]}")
    if salvate or errori:
        ctx.log(f"{NOME}: dal sito, in attesa degli open data: sedute {salvate}" + (f"; non lette: {errori}" if errori else ""))
    return {"dal_sito": len(salvate), **({"dal_sito_errori": errori} if errori else {})}


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 0.5))
    ricontrolla, massimo = int(cfg.get("ricontrolla", 3)), int(cfg.get("massimo_per_giro", 1000))
    lago = Lago(ctx.cartella)
    k_indice = f"leg{leg}-voti-indice"
    prima = lago.ultimo(NOME, k_indice)
    vecchio = {r["seduta"]: r for r in leggi(lago.leggi(prima["file"]))} if prima else {}
    indice = interroga(ENDPOINT, PREFISSI_V + INDICE.replace("{LEG}", leg_uri(leg)), pausa=pausa)
    if not indice:
        raise RuntimeError("indice delle votazioni vuoto: l'endpoint della Camera potrebbe avere un problema")
    presenti = set(lago.chiavi(NOME))
    ultime = {r["seduta"] for r in sorted(indice, key=lambda r: numero_seduta(r["seduta"]))[-ricontrolla:]} if ricontrolla > 0 else set()
    # da rifare: le sedute che mancano nel lago, quelle cambiate rispetto all'indice del giro prima, le ultime.
    # Senza un indice precedente (primo giro, o giro interrotto) una seduta già nel lago si tiene com'è.
    da_fare = [r for r in sorted(indice, key=lambda r: numero_seduta(r["seduta"]))
               if chiave(numero_seduta(r["seduta"]), leg) not in presenti or (vecchio and vecchio.get(r["seduta"]) != r) or r["seduta"] in ultime]
    nuove = cambiate = invariate = 0
    fallite = []
    for r in da_fare[:massimo]:
        s = r["seduta"]
        try:
            votazioni, voti = _seduta(s, pausa)
        except Exception as e:  # una seduta che non risponde non ferma le altre; il passo fallisce alla fine
            fallite.append(f"{numero_seduta(s)}: {str(e)[:120]}")
            continue
        k = chiave(numero_seduta(s), leg)
        esito = lago.salva(NOME, k, _comprimi({"seduta": s, "votazioni": votazioni, "voti": voti}), ENDPOINT, "json.gz")
        if not esito["nuovo"]:
            invariate += 1
        elif k in presenti:
            cambiate += 1
        else:
            nuove += 1
    sito = _dal_sito(ctx, lago, leg, indice, cfg)
    if fallite:
        raise RuntimeError(f"{len(fallite)} sedute non scaricate ({nuove} nuove salvate, si riprendono al giro dopo): {fallite[:5]}")
    # l'indice si salva solo alla fine: se il giro si ferma a metà, le sedute mancanti si rifanno al giro dopo
    if len(da_fare) <= massimo:
        lago.salva(NOME, k_indice, _comprimi(indice), ENDPOINT, "json.gz")
    ctx.log(f"{NOME}: {len(indice)} sedute con voti; {nuove} nuove, {cambiate} cambiate, {invariate} invariate, {max(0, len(da_fare) - massimo)} rimandate")
    return {"sedute": len(indice), "nuove": nuove, "cambiate": cambiate, "invariate": invariate, "rimandate": max(0, len(da_fare) - massimo), **sito}
