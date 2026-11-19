"""Votazioni elettroniche della Camera dal sito (documenti.camera.it), per le sedute che dati.camera.it non ha ancora.

Il sito pubblica la scheda di ogni votazione mentre la seduta è in corso; gli open data arrivano il pomeriggio del giorno
dopo (verso le 15 italiane), a volte più tardi. Per non restare un giorno intero col dibattito e senza i numeri, il giro
della notte legge dal sito le sedute che mancano negli open data e le salva nello stesso formato di `camera_voti`, con
`fonte: sito`: sono provvisorie, e si sostituiscono da sole quando la seduta compare negli open data.

La scheda dà nome, gruppo e voto di ogni deputato, senza identificativi: il deputato si riconosce dal nome nell'anagrafica
e il gruppo (o la componente del Misto) si prende dall'ultima seduta arrivata dagli open data. Se un nome non si riconosce
la seduta non si salva: meglio aspettare gli open data che attribuire un voto alla persona sbagliata.
"""

from __future__ import annotations

import html
import re
import time
import unicodedata
import urllib.error
import urllib.request

from .sparql import UA

SCHEDA = "https://documenti.camera.it/apps/votazioni/votazionitutte/schedavotazione.asp?Legislatura={leg}&RifVotazione={seduta}_{numero}&tipo=dettaglio"
# la scheda come la scrivono gli open data (dc:relation), così il link nei dati non cambia quando arrivano
SCHEDA_OCD = "http://documenti.camera.it/apps/votazioni/votazionitutte/schedavotazione.asp?Legislatura={leg}&RifVotazione={seduta}_{numero}&tipo=dettaglio"
ROMANI = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]

INTESTAZIONE = re.compile(r"<h1>\s*(Votazione[^<]*?)\s+n\.\s*(\d+)\s*</h1>.*?del\s*<strong>(\d{2})/(\d{2})/(\d{4})</strong>\s*seduta n\.\s*"
                          r"<strong>(\d+)</strong>(?:\s*presieduta da\s*<strong>([^<]*)</strong>)?", re.S | re.I)
TITOLO = re.compile(r"TITOLO DEL PROVVEDIMENTO.*?<h4>(.*?)(?:<span|</h4>|</div>)", re.S)
CONTO = re.compile(r'<p class="label">\s*([A-Z]+)\s*</p>.*?<p class="label">\s*(\d+)\s*</p>', re.S)
ESITO = re.compile(r"La Camera\s+(APPROVA|RESPINGE)", re.I)
RIGA = re.compile(r"<tr>\s*<td>([^<]+)</td>\s*<td>([^<]*)</td>\s*<td>\s*(?:<span[^>]*>)?([^<]+)", re.I)
# come gli open data chiamano i voti: chi non vota è «Non ha votato», con il motivo in nota
VOTI = {"favorevole": ("Favorevole", None), "contrario": ("Contrario", None), "astensione": ("Astensione", None),
        "astenuto": ("Astensione", None), "in missione": ("Non ha votato", "In missione"),
        "non ha partecipato": ("Non ha votato", "Non ha partecipato"), "presidente di turno": ("Non ha votato", "Presidente di turno")}


# il tipo dalla descrizione, come lo scrivono gli open data: «ODG 9/2830 E ABB/4», «ARTICOLO 1», «MOZ 1-346», «RIS 6-287»
ODG = re.compile(r"\bODG\s+(9/(\d{1,5})\S*(?:\s+E\s+ABB)?/(\d{1,4}))\b")
ARTICOLO = re.compile(r"\bARTICOLO\s+(\d+(?:-[a-z]+)?)\b", re.I)


# l'atto votato: «DDL 3133-A - EM 1.1», «PDL 2830 E ABB - VOTO FINALE», «ODG 9/3133-A/4». -A è il testo della commissione
# dello stesso atto, -B (-C…) l'atto tornato dall'altro ramo
ATTO = re.compile(r"\b(?:(?:PDL|DDL|A\.C\.)\s*\.?\s*(?:n\.\s*)?|ODG\s+9/)(\d{1,5})(?:-([A-Z]))?\b")


def atto_votato(descrizione: str | None, leg: int) -> str | None:
    m = ATTO.search(descrizione or "")
    if not m:
        return None
    numero, lettera = m.groups()
    return f"ac{leg}_{numero}" if lettera in (None, "A") else f"ac{leg}_{numero}-{lettera}"


def tipo_e_titolo(descrizione: str | None, finale: bool, leg: int) -> dict:
    """Tipo, titolo e (per gli ordini del giorno) riferimento dell'atto di indirizzo, dalla descrizione della scheda."""
    d = descrizione or ""
    if finale:
        return {"tipo": "Finale atto Camera", "titolo": "Votazione finale "}
    if m := ODG.search(d):
        return {"tipo": "Ordine del Giorno", "titolo": f"Votazione Ordine del giorno {m.group(1)} ",
                "aic": f"http://dati.camera.it/ocd/aic.rdf/aic9_{int(m.group(2)):05d}_{int(m.group(3)):03d}_{leg}"}
    if m := ARTICOLO.search(d):
        return {"tipo": "Articolo", "titolo": f"Votazione Articolo {m.group(1)} "}
    if re.match(r"\s*MOZ\b", d):
        return {"tipo": "Mozione", "titolo": "Votazione "}
    if re.match(r"\s*R(?:IS\b|\d-)", d):
        return {"tipo": "Risoluzione", "titolo": "Votazione "}
    return {"tipo": "Altre", "titolo": "Votazione "}


def romano(n: int) -> str:
    out = ""
    for valore, segno in ROMANI:
        while n >= valore:
            out, n = out + segno, n - valore
    return out


def chiave_nome(nome: str) -> str:
    """«MULE' GIORGIO» e «MULÈ GIORGIO» sono la stessa chiave: senza accenti, apostrofi e spazi doppi."""
    senza = unicodedata.normalize("NFD", html.unescape(nome)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z ]", " ", senza)).strip().upper()


def riconosci(nomi: set[str], persone: list[dict], in_carica: set[str] | None = None) -> dict[str, str]:
    """Dal nome scritto nella scheda («COGNOME NOME») all'uri della persona. Prima il nome intero; poi, perché il sito usa
    il nome d'uso («CUPERLO GIANNI» per Giovanni), il solo cognome, se fra i deputati rimasti (quelli in carica, quando si
    sanno) ce n'è uno solo. Un nome che resta ambiguo non compare nel risultato: non si sceglie a caso."""
    interi: dict[str, set[str]] = {}
    for p in persone:
        interi.setdefault(chiave_nome(f"{p.get('cognome', '')} {p.get('nome', '')}"), set()).add(p["persona"])
    out = {n: next(iter(interi[k])) for n in nomi if len(interi.get(k := chiave_nome(n), ())) == 1}
    presi = set(out.values())
    for n in sorted(nomi - set(out)):
        k = chiave_nome(n)
        candidati = {p["persona"] for p in persone if p["persona"] not in presi and (c := chiave_nome(p.get("cognome", "")))
                     and (k == c or k.startswith(c + " "))}
        if in_carica and len(candidati & in_carica) >= 1:
            candidati &= in_carica
        if len(candidati) == 1:
            out[n] = candidati.pop()
    return out


def leggi_scheda(pagina: str) -> dict | None:
    """Una scheda di votazione del sito; None se la pagina non è una scheda (votazione che non esiste)."""
    m = INTESTAZIONE.search(pagina)
    if not m:
        return None
    tipo, numero, giorno, mese, anno, seduta, presidente = m.groups()
    t = TITOLO.search(pagina)
    conti = {k.lower(): int(v) for k, v in CONTO.findall(pagina)}
    e = ESITO.search(pagina)
    voti = [(html.unescape(nome).strip(), html.unescape(gruppo).strip(), html.unescape(voto).strip())
            for nome, gruppo, voto in RIGA.findall(pagina)]
    return {"numero": int(numero), "seduta": int(seduta), "data": f"{anno}{mese}{giorno}", "finale": "finale" in tipo.lower(),
            "segreta": "segret" in tipo.lower(), "presidente": html.unescape(presidente or "").strip() or None,
            "descrizione": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t.group(1)))).strip() if t else None,
            "conti": conti, "approvato": None if not e else e.group(1).upper() == "APPROVA", "voti": voti}


def _deputato(persona: str, leg: int) -> str:
    return re.sub(r"persona\.rdf/p(\d+)$", rf"deputato.rdf/d\g<1>_{leg}", persona)


def _persona(deputato: str) -> str:
    return re.sub(r"deputato\.rdf/d(\d+)_\d+$", r"persona.rdf/p\g<1>", deputato)


def in_formato_ocd(schede: list[dict], leg: int, persone: list[dict], gruppi: dict[str, dict]) -> dict:
    """Le schede di una seduta nel formato dei file di `camera_voti` (votazioni e voti come li dà dati.camera.it).
    `persone`: l'anagrafica dei deputati della legislatura; `gruppi`: per deputato, gruppo e componente nell'ultima
    seduta arrivata dagli open data (chi c'è lì è in carica)."""
    seduta = schede[0]["seduta"]
    votazioni, voti, ignoti = [], [], set()
    scritti = {n for s in schede for n, _g, _v in s["voti"]} | {s["presidente"] for s in schede if s["presidente"]}
    nomi = riconosci(scritti, persone, {_persona(d) for d in gruppi})

    def uri(nome: str | None) -> str | None:
        persona = nomi.get(nome) if nome else None
        if nome and not persona:
            ignoti.add(nome)
        return _deputato(persona, leg) if persona else None

    atto = None
    for s in sorted(schede, key=lambda s: s["numero"]):
        v = f"http://dati.camera.it/ocd/votazione.rdf/vs{leg}_{seduta}_{s['numero']:03d}"
        # la scheda nomina l'atto nella prima votazione della serie («DDL 3133-A - EM 1.1») e poi scrive solo «EM 1.2»:
        # l'atto vale finché non ne compare un altro o si passa a mozioni e risoluzioni
        if re.match(r"\s*(?:MOZ\b|R(?:IS\b|\d-))", s["descrizione"] or ""):
            atto = None
        else:
            atto = atto_votato(s["descrizione"], leg) or atto
        c = s["conti"]
        riga = {"votazione": v, "numero": f"{seduta}{s['numero']:03d}", "data": s["data"], "descrizione": s["descrizione"],
                **tipo_e_titolo(s["descrizione"], s["finale"], leg),
                "finale": "1" if s["finale"] else "0", "segreta": "1" if s["segreta"] else "0",
                # la fiducia si vota per appello nominale, non con il voto elettronico: fra le schede non c'è
                "fiducia": "0", "scheda": SCHEDA_OCD.format(leg=romano(leg), seduta=seduta, numero=s["numero"])}
        for campo in ("presenti", "votanti", "astenuti", "maggioranza", "favorevoli", "contrari"):
            if campo in c:
                riga[campo] = str(c[campo])
        if s["approvato"] is not None:
            riga["approvato"] = "1" if s["approvato"] else "0"
        if presidente := uri(s["presidente"]):
            riga["presidente"] = presidente
        if atto and riga["tipo"] != "Ordine del Giorno":         # come negli open data: l'ordine del giorno ha il suo riferimento
            riga["atto"] = f"http://dati.camera.it/ocd/attocamera.rdf/{atto}"
        votazioni.append(riga)
        for nome, _sigla, voto in s["voti"]:
            deputato = uri(nome)
            if not deputato:
                continue
            tipo, nota = VOTI.get(voto.lower(), (voto, None))      # nel voto segreto resta la parola del sito: «ha votato»
            r = {"votazione": v, "deputato": deputato, "tipo": tipo, **gruppi.get(deputato, {})}
            if nota:
                r["nota"] = nota
            voti.append(r)
    if ignoti:
        raise RuntimeError(f"seduta {seduta}: {len(ignoti)} nomi non riconosciuti nell'anagrafica ({sorted(ignoti)[:5]})")
    voti.sort(key=lambda r: (r["votazione"], r["deputato"], r["tipo"]))
    return {"seduta": f"http://dati.camera.it/ocd/seduta.rdf/s{leg}_{seduta}", "votazioni": votazioni, "voti": voti, "fonte": "sito"}


def gruppi_dai_voti(voti: list[dict]) -> dict[str, dict]:
    """Gruppo e componente di ogni deputato nell'ultima votazione di un file degli open data."""
    out: dict[str, dict] = {}
    for r in sorted(voti, key=lambda r: r["votazione"]):
        out[r["deputato"]] = {k: r[k] for k in ("gruppo", "componente") if r.get(k)}
    return out


def _pagina(leg: int, seduta: int, numero: int) -> str:
    req = urllib.request.Request(SCHEDA.format(leg=romano(leg), seduta=seduta, numero=numero), headers={"User-Agent": UA})
    for tentativo in (1, 2, 3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("latin-1")
        except (urllib.error.URLError, TimeoutError, ConnectionResetError):
            if tentativo == 3:
                raise
            time.sleep(10 * tentativo)
    raise RuntimeError("non raggiungibile")


def schede_seduta(leg: int, seduta: int, pausa: float = 1.0, massimo: int = 600, pagina=_pagina) -> list[dict]:
    """Tutte le schede di una seduta: la numerazione parte da 1 e si ferma alla prima che non esiste."""
    out = []
    for numero in range(1, massimo + 1):
        s = leggi_scheda(pagina(leg, seduta, numero))
        if not s or s["seduta"] != seduta:
            break
        out.append(s)
        time.sleep(pausa)
    return out
