"""Votazioni elettroniche dell'Assemblea del Senato da dati.senato.it: ogni votazione e il voto di ogni senatore
(favorevole, contrario, astenuto, in congedo o missione, presente non votante).

Un file nel lago per seduta (`leg19-senato-voti-sed0167`, JSON compresso). senato.it blocca l'IP dopo qualche centinaio
di richieste ravvicinate, quindi le richieste si raggruppano: una per le votazioni di `SEDUTE_PER_RICHIESTA` sedute,
poi i voti dei singoli a gruppi di `BLOCCO` votazioni anche di sedute diverse (45 × circa 206 senatori resta sotto le
10 mila righe che l'endpoint restituisce al massimo). `massimo_richieste_per_giro` ferma il passo senza errore: le
sedute rimaste passano al giro dopo. Niente VALUES né BIND: l'endpoint risponde 400. Ogni notte: le sedute nuove e le ultime `ricontrolla` (i voti arrivano in ritardo).
"""

from __future__ import annotations

import gzip
import json
import time
import urllib.parse

from ..lago import Lago
from .sparql import _richiesta

NOME = "senato_voti"
ENDPOINT = "https://dati.senato.it/sparql"
SA = "http://dati.senato.it/sedutaassemblea/"
P = "PREFIX osr:<http://dati.senato.it/osr/> PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> "
PS = f"PREFIX sa:<{SA}> "     # uri delle sedute abbreviati: l'uri intero, codificato nell'URL, costa circa 60 caratteri
SEDUTE = P + "SELECT ?seduta ?numero ?data WHERE { ?seduta a osr:SedutaAssemblea ; osr:legislatura {LEG} ; osr:numeroSeduta ?numero . OPTIONAL { ?seduta osr:dataSeduta ?data } } LIMIT 5000"
# ?atto: il ddl votato (osr:oggetto -> relativoA), nella stessa richiesta per non aggiungerne altre
VOTAZIONI = P + PS + """SELECT ?seduta ?votazione ?numero ?label ?tipo ?presenti ?votanti ?favorevoli ?contrari ?astenuti ?maggioranza ?esito ?atto WHERE {
 ?votazione a osr:Votazione ; osr:seduta ?seduta . FILTER({SEDUTE}) OPTIONAL { ?votazione osr:numero ?numero } OPTIONAL { ?votazione rdfs:label ?label }
 OPTIONAL { ?votazione osr:tipoVotazione ?tipo } OPTIONAL { ?votazione osr:presenti ?presenti } OPTIONAL { ?votazione osr:votanti ?votanti }
 OPTIONAL { ?votazione osr:favorevoli ?favorevoli } OPTIONAL { ?votazione osr:contrari ?contrari } OPTIONAL { ?votazione osr:astenuti ?astenuti }
 OPTIONAL { ?votazione osr:maggioranza ?maggioranza } OPTIONAL { ?votazione osr:esito ?esito }
 OPTIONAL { ?votazione osr:oggetto ?o . ?o osr:relativoA ?atto } } LIMIT 10000"""
# un gruppo di tratti (seduta, dal numero, al numero): un ramo UNION per seduta con l'uri costante. Un OR di sedute
# in un FILTER fa leggere a Virtuoso tutti i voti (502), e l'endpoint non accetta VALUES né BIND
VOTI = P + PS + """SELECT ?v ?n ?p ?senatore WHERE { {TRATTI}
 FILTER(?p = osr:favorevole || ?p = osr:contrario || ?p = osr:astenuto || ?p = osr:inCongedoMissione || ?p = osr:presenteNonVotante) } LIMIT 10000"""
TRATTO = "{ ?v osr:seduta {S} ; osr:numero ?n ; ?p ?senatore . FILTER(?n >= {DA} && ?n <= {A}) }"
BLOCCO = 45
# il WAF rifiuta URL lunghi con 403: 1.346 caratteri passano, 2.706 no (1/11). Sedute e tratti per richiesta stanno
# sotto LIMITE_URL (votazioni di 4 sedute: 1.305; voti in 4 tratti: 1.080), e una query più lunga si ferma prima di partire
LIMITE_URL = 1340
SEDUTE_PER_RICHIESTA = 4
TRATTI_PER_RICHIESTA = 4


class Tetto(Exception):
    """Raggiunto il massimo di richieste del giro: non è un errore, il resto si fa al giro dopo."""


def chiave(numero: int, leg: int) -> str:
    return f"leg{leg}-senato-voti-sed{numero:04d}"


def leggi(corpo: bytes):
    return json.loads(gzip.decompress(corpo))


def gruppi(numeri: list[tuple[str, int]], blocco: int = BLOCCO, max_tratti: int = TRATTI_PER_RICHIESTA) -> list[list[tuple[str, int, int]]]:
    """Le votazioni (seduta, numero), ordinate, a gruppi di al massimo `blocco` votazioni e `max_tratti` sedute;
    ogni gruppo come tratti (seduta, dal, al)."""
    out, tratti, n_voti = [], {}, 0
    for s, n in numeri:
        if n_voti == blocco or (s not in tratti and len(tratti) == max_tratti):
            out.append([(x, min(ns), max(ns)) for x, ns in tratti.items()])
            tratti, n_voti = {}, 0
        tratti.setdefault(s, []).append(n)
        n_voti += 1
    if tratti:
        out.append([(x, min(ns), max(ns)) for x, ns in tratti.items()])
    return out


def corto(uri: str) -> str:
    """`sa:23908` per le sedute dell'Assemblea, l'uri fra <> per il resto."""
    resto = uri[len(SA):] if uri.startswith(SA) else ""
    return f"sa:{resto}" if resto.isdigit() else f"<{uri}>"


def lunghezza_url(q: str) -> int:
    return len(ENDPOINT) + 1 + len(urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"}))


def _lotto(lotto: list[dict], chiedi) -> dict[str, tuple[list, list]]:
    """Votazioni e voti di un lotto di sedute, per uri della seduta."""
    righe = chiedi(VOTAZIONI.replace("{SEDUTE}", " || ".join(f"?seduta = {corto(s['seduta'])}" for s in lotto)))
    if len(righe) >= 10000:
        raise RuntimeError("votazioni: risposta tagliata a 10 mila righe")
    votazioni: dict[str, list] = {s["seduta"]: [] for s in lotto}
    for r in righe:
        votazioni[r.pop("seduta")].append(r)
    numeri = sorted({(s, int(v["numero"])) for s, vs in votazioni.items() for v in vs if (v.get("numero") or "").isdigit()})
    seduta_di = {v["votazione"]: s for s, vs in votazioni.items() for v in vs}
    voti: dict[str, list] = {s["seduta"]: [] for s in lotto}
    for g in gruppi(numeri):
        tratti = " UNION ".join(TRATTO.replace("{S}", corto(s)).replace("{DA}", str(da)).replace("{A}", str(a)) for s, da, a in g)
        blocco = chiedi(VOTI.replace("{TRATTI}", tratti))
        if len(blocco) >= 10000:
            raise RuntimeError(f"voti: risposta tagliata a 10 mila righe ({g[0][0]} {g[0][1]}…)")
        for r in blocco:
            voti[seduta_di[r["v"]]].append(r)
    for vs in voti.values():
        vs.sort(key=lambda r: (int(r["n"]), r["senatore"], r["p"]))
    return {s: (votazioni[s], voti[s]) for s in votazioni}


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, pausa = int(cfg["legislatura"]), float(cfg.get("pausa_secondi", 5))
    massimo, ricontrolla = int(cfg.get("massimo_sedute_per_giro", 60)), int(cfg.get("ricontrolla", 5))
    lago = Lago(ctx.cartella)
    sedute = sorted(_richiesta(ENDPOINT, SEDUTE.replace("{LEG}", str(leg)), 2), key=lambda r: int(r["numero"]))
    time.sleep(pausa)
    presenti = set(lago.chiavi(NOME))
    ultime = sedute[-ricontrolla:] if ricontrolla > 0 else []  # [-0:] darebbe tutto
    mancano = [s for s in reversed(sedute) if chiave(int(s["numero"]), leg) not in presenti]
    fatti, fallite, richieste = 0, [], 1
    tetto = int(cfg.get("massimo_richieste_per_giro", 150))

    def chiedi(q: str) -> list[dict]:
        nonlocal richieste
        if lunghezza_url(q) > LIMITE_URL:  # il WAF risponderebbe 403: meglio fermarsi senza chiedere
            raise RuntimeError(f"query di {lunghezza_url(q)} caratteri, oltre {LIMITE_URL}")
        if richieste >= tetto:
            raise Tetto()
        richieste += 1
        try:
            return _richiesta(ENDPOINT, q, 2)
        finally:
            time.sleep(pausa)

    da_fare = list({x["seduta"]: x for x in ultime + mancano}.values())[:massimo]
    for i in range(0, len(da_fare), SEDUTE_PER_RICHIESTA):
        lotto = da_fare[i:i + SEDUTE_PER_RICHIESTA]
        try:
            risultati = _lotto(lotto, chiedi)
        except Tetto:
            break
        except Exception as e:  # al primo errore ci si ferma: insistere con senato.it allunga il blocco
            fallite.append(f"{lotto[0]['numero']}-{lotto[-1]['numero']}: {str(e)[:100]}")
            break
        for s in lotto:
            votazioni, voti = risultati[s["seduta"]]
            corpo = gzip.compress(json.dumps({"seduta": s, "votazioni": votazioni, "voti": voti}, ensure_ascii=False, sort_keys=True).encode(), mtime=0)
            lago.salva(NOME, chiave(int(s["numero"]), leg), corpo, ENDPOINT, "json.gz")
            fatti += 1
    nuove = {chiave(int(s["numero"]), leg) for s in da_fare[:fatti]}
    rimandate = sum(1 for s in mancano if chiave(int(s["numero"]), leg) not in nuove)
    ctx.log(f"{NOME}: {len(sedute)} sedute; {fatti} scaricate, {rimandate} rimandate, {richieste} richieste")
    if fallite:
        raise RuntimeError(f"dati.senato.it ha smesso di rispondere, si riprende al giro dopo: {fallite}")
    return {"sedute": len(sedute), "scaricate": fatti, "rimandate": rimandate, "richieste": richieste}
