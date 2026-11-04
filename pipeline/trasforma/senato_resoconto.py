"""Dal resoconto stenografico del Senato in Akoma Ntoso agli stessi record della Camera: `Sitting`, `AgendaItem`
(le sezioni del dibattito con un titolo), `Speech` (parola per parola) con la persona di dati.senato.it e la carica
(Presidente, Relatore, Presidente del Consiglio…), e le didascalie d'Aula come `Reaction`. Trasformazione pura.

Il testo canonico è il parlato senza didascalie e senza il gruppo dichiarato in testa («(M5S).»), come alla Camera.
"""

from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET

from .camera_resoconto import reazioni

AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03}"
# la sigla del gruppo di chi parla, anche con una parentesi dentro: «(M5S)», «(Aut (SVP-Patt, Cb, SCN))», «(Cd'I-UDC-NM (NcI, CI, IaC)-MAIE-CP)»
GRUPPO = re.compile(r"^\(((?:[^()]|\([^()]{1,40}\)){1,60})\)$")


def sigla(t: str) -> bool:
    """Ha la forma di una sigla di gruppo («FdI», «Misto-Avanti PSI», «Aut (SVP-Patt, Cb, SCN)»), non di una didascalia
    («ore 10,05», «Reiterate proteste», «Il Presidente e l'Assemblea si levano in piedi»): parole brevi con la maiuscola."""
    parole = [w for w in re.split(r"[\s,()-]+", t) if w]
    return bool(parole) and all(len(w) <= 8 and w[0].isupper() for w in parole) \
        and (t.startswith("Misto") or sum(c.isupper() for c in t) >= 2)


def _h(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def _paragrafo(p: ET.Element) -> tuple[str, list[str]]:
    """Testo del paragrafo senza le didascalie (corsivo fra parentesi), e le didascalie."""
    parti, didascalie = [p.text or ""], []
    for c in p:
        t = "".join(c.itertext()).strip()
        if c.tag == AKN + "i" and t.startswith("(") and t.endswith(")"):
            didascalie.append(t)
        else:
            parti.append("".join(c.itertext()))
        parti.append(c.tail or "")
    return re.sub(r"\s+", " ", "".join(parti)).strip(), didascalie


PAR = re.compile(r"<p([^>]*)>(.*?)</p>", re.S | re.I)
LINK = re.compile(r'^\s*<a[^>]*href="[^"]*tipodoc=sanasen&(?:amp;)?id=(\d+)"[^>]*>([^<]+)</a>(.*)$', re.S | re.I)
TAG = re.compile(r"<[^>]+>")
CORSIVO = re.compile(r"<i>(.*?)</i>", re.S | re.I)
# lo stesso oratore senza link, dopo che il Presidente gli ha dato la parola: «DAMANTE <i>(M5S)</i>. Signora Presidente…»
NOME_PIANO = re.compile(r"^([A-ZÀ-Ý][A-ZÀ-Ý'\- ]+?(?: [A-ZÀ-Ý][a-zà-ÿ']+)*)\s*(\((?:[^()]|\([^()]{1,40}\)){1,60}\))?\s*(,\s*[^.]{1,120})?\.\s+(.*)$", re.S)


def _testo(frammento: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub("", frammento)).replace("\xa0", " ")).strip()


SHOW_DOC = "https://www.senato.it/show-doc?leg={leg}&tipodoc=Resaula&id={id}"


def indirizzo_resoconto(url: str | None, leg: int, numero: int, documenti: dict[int, int] | None = None) -> str | None:
    """L'indirizzo del resoconto ufficiale su senato.it. Dal grezzo del bulk (`…#Leg19/Atto…/resaula/01526543-ra.akn.xml`)
    l'id del documento è il numero del file senza zeri davanti; una pagina importata ha già l'indirizzo show-doc. Per i
    resoconti importati con il solo uri di dati.senato.it vale l'id del file del bulk per lo stesso numero di seduta
    (`documenti`, numero -> id), se c'è."""
    url = url or ""
    m = re.search(r"/resaula/0*(\d+)-ra\.akn\.xml$", url)
    if m:
        return SHOW_DOC.format(leg=leg, id=int(m.group(1)))
    if url.startswith("https://www.senato.it/show-doc?"):
        return url
    if documenti and numero in documenti:
        return SHOW_DOC.format(leg=leg, id=documenti[numero])
    return None


def _da_html(pagina: str, fonte: dict, leg: int, documenti: dict | None = None) -> dict:
    """Le sedute pubblicate solo come pagina web (show-doc, part=doc_dc): titoli in grassetto centrati, ogni intervento
    apre con il link al senatore (lo stesso id di dati.senato.it), i paragrafi senza link continuano l'intervento."""
    t = re.search(r"seduta n\.\s*(\d+)\s+del\s+(\d{2})/(\d{2})/(\d{4})", pagina, re.I)
    numero, data = int(t.group(1)), f"{t.group(4)}-{t.group(3)}-{t.group(2)}"
    s_uri = f"it:senato:{leg}:sed{numero:04d}"
    nodi = [{"label": "Sitting", "uri": s_uri, "chamber": "senato", "body": f"it:senato:{leg}:aula", "number": numero, "date": data,
             "status": "held", "kind": "assembly_verbatim", "source": "senato_html", "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta"),
             "record_url": indirizzo_resoconto(fonte.get("url"), leg, numero, documenti)}]
    archi, testi = [], []
    punti: list[dict] = []
    titolo, in_attesa, punto = None, "", None
    interventi: list[dict] = []
    corrente, presidente, ids = None, None, {}

    def apri(etichetta, pid, ruolo, gruppo, testo):
        nonlocal corrente, punto
        if punto is None or punto["title"] != titolo:
            n = len(punti) + 1
            punto = {"label": "AgendaItem", "uri": f"{s_uri}:tit{n:05d}", "order": n, "title": titolo}
            punti.append(punto)
        corrente = {"punto": punto, "etichetta": etichetta, "pid": pid, "ruolo": ruolo, "gruppo": gruppo, "testo": "", "reazioni": []}
        interventi.append(corrente)
        aggiungi(testo)

    def aggiungi(frammento):
        """Il testo senza le didascalie in corsivo fra parentesi, che diventano reazioni."""
        dids = [d for d in (_testo(x) for x in CORSIVO.findall(frammento)) if d.startswith("(") and d.rstrip(".").endswith(")")]
        pulito = CORSIVO.sub(lambda m: "\x00" if _testo(m.group(1)) in dids else m.group(0), frammento)
        pulito = re.sub(r"([.!?])((?:\s|<[^>]+>)*)\x00\s*\.", r"\1\2", pulito).replace("\x00", "")   # «PNRR. (Applausi).» -> «PNRR.»
        x = re.sub(r"\s+([.,;:])", r"\1", re.sub(r"^[.,:;]\s*", "", _testo(pulito))).strip()
        at = len(corrente["testo"]) + (2 if corrente["testo"] else 0)
        if x:
            corrente["testo"] = f"{corrente['testo']}\n\n{x}" if corrente["testo"] else x
        corrente["reazioni"] += [(at, d) for d in dids]

    for attr, dentro in PAR.findall(pagina):
        dentro = re.sub(r"<a[^>]*>\s*</a>", "", dentro)
        x = _testo(dentro)
        if not x:
            continue
        centrato = "center" in attr.lower()
        if centrato and x.lower() in ("allegato a", "allegato b"):
            break
        if x.lower().startswith("presidenza del"):          # il cambio di presidenza è stampato come un titolo
            continue
        grassetto = _testo(" ".join(re.findall(r"<b>(.*?)</b>", dentro, re.S | re.I)))
        if (in_attesa or (0 < len(x) < 400 and len(grassetto) >= 0.9 * len(x))) and not LINK.match(dentro):
            nuovo = f"{in_attesa} {x}".strip()
            if nuovo.endswith(":") and not in_attesa:
                in_attesa = nuovo
                continue
            # l'intestazione del resoconto non è un punto: gli interventi prima del primo titolo stanno senza titolo
            titolo, in_attesa, corrente = (None if nuovo.upper() == "RESOCONTO STENOGRAFICO" else nuovo), "", None
            continue
        if centrato:
            continue
        m = LINK.match(dentro)
        if m:
            pid, nome, resto = m.group(1), _testo(m.group(2)), m.group(3)
            ids[nome.upper()] = pid
            testa = re.match(r"^\s*(?:<i>\s*\(((?:[^()<]|\([^()<]{1,40}\)){1,60})\)\s*</i>)?\s*(?:,\s*(?:<i>)?([^.<]{1,120})(?:</i>)?)?\s*\.\s*", resto)
            gruppo = testa.group(1) if testa else None
            ruolo = testa.group(2).strip() if testa and testa.group(2) else None
            if nome.upper() == "PRESIDENTE":
                presidente, ruolo = pid, "PRESIDENTE"
            didascalia = gruppo if gruppo and not sigla(gruppo) else None    # «(ore 10,02)» al posto della sigla
            apri(nome, pid, ruolo, None if didascalia else gruppo, resto[testa.end():] if testa else resto)
            if didascalia:
                corrente["reazioni"].insert(0, (0, f"({didascalia})"))
            continue
        if re.match(r"^PRESIDENTE\s*\.", x):
            apri("PRESIDENTE", presidente, "PRESIDENTE", None, re.sub(r"^\s*PRESIDENTE\s*\.", "", dentro))
            continue
        piano = NOME_PIANO.match(x)
        g = piano.group(2)[1:-1] if piano and piano.group(2) else None
        if piano and (piano.group(1).upper() in ids or (g and sigla(g))):
            nome = piano.group(1).strip()
            corpo_p = re.sub(r"^.*?\.\s+", "", dentro, count=1, flags=re.S)
            apri(nome, ids.get(nome.upper()), piano.group(3).lstrip(", ").strip() if piano.group(3) else None,
                 g if g and sigla(g) else None, corpo_p)
            if g and not sigla(g):
                corrente["reazioni"].insert(0, (0, f"({g})"))
            continue
        if corrente is None:
            continue
        if x.startswith("(") and x.rstrip(".").endswith(")"):    # didascalia da sola: «(Applausi dal Gruppo PD)»
            corrente["reazioni"].append((len(corrente["testo"]), x.rstrip(".")))
            continue
        aggiungi(dentro)

    usati, ordine = set(), {}
    for i, x in enumerate(interventi, 1):
        if not (x["testo"] or x["reazioni"]):
            continue
        p = x["punto"]
        if p["uri"] not in usati:
            usati.add(p["uri"])
            nodi.append(p)
            archi.append({"type": "HAS_ITEM", "from": s_uri, "to": p["uri"], "order": p["order"]})
            if p["title"] and re.search(r"(?i)disegn[oi] di legge", p["title"]):   # «Discussione del disegno di legge: (1162) …»
                archi += [{"type": "ABOUT", "from": p["uri"], "to_ref": f"ddl:{n}"} for n in dict.fromkeys(re.findall(r"\((\d+(?:-[A-Z]+)?)\)", p["title"]))]
        ordine[p["uri"]] = ordine.get(p["uri"], 0) + 1
        uri = f"{s_uri}:int{i:05d}"
        nodi.append({"label": "Speech", "uri": uri, "order": ordine[p["uri"]], "hash": _h(x["testo"]), "text_ref": f"speech:{uri}",
                     "speaker_label": x["etichetta"] or None, "declared_group": x["gruppo"], "anchor": None})
        archi.append({"type": "HAS_SPEECH", "from": p["uri"], "to": uri, "order": ordine[p["uri"]]})
        if x["pid"]:
            archi.append({"type": "BY", "from": uri, "to": f"it:person:senato:{x['pid']}", "as_group": x["gruppo"], "as_office": x["ruolo"]})
        for k, (offset, d) in enumerate(x["reazioni"]):
            for z, r in enumerate(reazioni(d)):
                r_uri = f"{uri}:r{k + 1}.{z + 1}"
                nodi.append({"label": "Reaction", "uri": r_uri, "kind": r["kind"], "offset": offset, "raw": r["text"]})
                archi.append({"type": "DURING", "from": r_uri, "to": uri})
                if r["from"]:
                    archi.append({"type": "FROM", "from": r_uri, "to_ref": r["from"]})
        testi.append({"ref": f"speech:{uri}", "text": x["testo"], "hash": _h(x["testo"])})
    return {"nodi": nodi, "archi": archi, "testi": testi}


def trasforma(corpo: bytes, fonte: dict, leg: int = 19, documenti: dict[int, int] | None = None) -> dict:
    if corpo.lstrip()[:15].lower() == b"<!doctype html>":
        return _da_html(corpo.decode("utf-8"), fonte, leg, documenti)
    radice = ET.fromstring(corpo)
    numero = int(radice.find(f".//{AKN}FRBRnumber").get("value"))
    data = radice.find(f".//{AKN}FRBRdate").get("date")
    s_uri = f"it:senato:{leg}:sed{numero:04d}"
    persone = {e.get("id"): e.get("href") for e in radice.iter(AKN + "TLCPerson")}
    ruoli = {e.get("id"): e.get("showAs") for e in radice.iter(AKN + "TLCRole")}
    padre = {c: p for p in radice.iter() for c in p}
    seduta = {"label": "Sitting", "uri": s_uri, "chamber": "senato", "body": f"it:senato:{leg}:aula", "number": numero, "date": data,
              "status": "held", "kind": "assembly_verbatim", "source": "senato_akn", "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta"),
              "record_url": indirizzo_resoconto(fonte.get("url"), leg, numero, documenti)}
    nodi, archi, testi = [seduta], [], []
    punti: dict[ET.Element, dict] = {}

    def punto_di(e: ET.Element) -> dict:
        """La sezione con titolo più vicina sopra l'intervento; senza titolo, un punto di servizio della seduta."""
        x = padre.get(e)
        while x is not None:
            if x.tag == AKN + "debateSection":
                h = x.find(AKN + "heading")
                titolo = re.sub(r"\s+", " ", "".join(h.itertext())).strip() if h is not None else ""
                if titolo:
                    if x not in punti:
                        n = len(punti) + 1
                        punti[x] = {"label": "AgendaItem", "uri": f"{s_uri}:{x.get('id') or n}", "order": n, "title": titolo}
                        nodi.append(punti[x])
                        archi.append({"type": "HAS_ITEM", "from": s_uri, "to": punti[x]["uri"], "order": n})
                        for b in x.findall(AKN + "block"):        # gli atti in discussione: <block name="Atto"> con tipo e numero
                            tipo, num = b.findtext(AKN + "docType"), (b.findtext(AKN + "docNumber") or "").strip()
                            if tipo in ("DDL", "Doc") and num:
                                archi.append({"type": "ABOUT", "from": punti[x]["uri"], "to_ref": f"{tipo.lower()}:{num}"})
                    return punti[x]
            x = padre.get(x)
        if None not in punti:
            punti[None] = {"label": "AgendaItem", "uri": f"{s_uri}:tit00000", "order": 0, "title": None}
            nodi.append(punti[None])
            archi.append({"type": "HAS_ITEM", "from": s_uri, "to": punti[None]["uri"], "order": 0})
        return punti[None]

    # chi è chi: l'etichetta di ogni blocco (FURLAN, PRESIDENTE) -> persona e carica. Il presidente di turno cambia
    # durante la seduta: vale l'ultimo blocco «PRESIDENTE» incontrato.
    blocchi = list(radice.iter(AKN + "speech"))
    nomi: dict[str, tuple] = {}
    for sp in blocchi:
        da = sp.find(AKN + "from")
        etichetta = re.sub(r"\s+", " ", "".join(da.itertext())).strip().upper() if da is not None else ""
        href = persone.get((sp.get("by") or "").lstrip("#"))
        if etichetta and href and etichetta != "PRESIDENTE":
            nomi.setdefault(etichetta, (href, ruoli.get((sp.get("as") or "").lstrip("#"))))
    # un altro oratore dentro il blocco: «PRESIDENTE.», «BORGHI.», e con gli omonimi «FLORIDIA Barbara.» (la sigla in corsivo è già tolta)
    testa = re.compile(r"^([A-ZÀ-ÖØ-Ý'][A-ZÀ-ÖØ-Ý' ]{2,60}?(?: [A-ZÀ-ÖØ-Ý][a-zà-ÿ']+)?)\s*\.\s+")
    ordine: dict[str, int] = {}
    presidente = (None, "PRESIDENTE")
    n_int = 0

    def nuovo_intervento(punto, etichetta, href, ruolo):
        nonlocal n_int
        n_int += 1
        ordine[punto["uri"]] = ordine.get(punto["uri"], 0) + 1
        return {"uri": f"{s_uri}:int{n_int:05d}", "punto": punto, "etichetta": etichetta, "href": href, "ruolo": ruolo,
                "gruppo": None, "testo": "", "reazioni": [], "ordine": ordine[punto["uri"]]}

    def chiudi(x):
        if not x or not (x["testo"] or x["reazioni"]):
            return
        m = re.search(r"/Persona/(\d+)", x["href"] or "")
        nodi.append({"label": "Speech", "uri": x["uri"], "order": x["ordine"], "hash": _h(x["testo"]), "text_ref": f"speech:{x['uri']}",
                     "speaker_label": x["etichetta"] or None, "declared_group": x["gruppo"], "anchor": None})
        archi.append({"type": "HAS_SPEECH", "from": x["punto"]["uri"], "to": x["uri"], "order": x["ordine"]})
        if m:
            archi.append({"type": "BY", "from": x["uri"], "to": f"it:person:senato:{m.group(1)}", "as_group": x["gruppo"], "as_office": x["ruolo"]})
        for k, (offset, d) in enumerate(x["reazioni"]):
            for z, r in enumerate(reazioni(d)):
                r_uri = f"{x['uri']}:r{k + 1}.{z + 1}"
                nodi.append({"label": "Reaction", "uri": r_uri, "kind": r["kind"], "offset": offset, "raw": r["text"]})
                archi.append({"type": "DURING", "from": r_uri, "to": x["uri"]})
                if r["from"]:
                    archi.append({"type": "FROM", "from": r_uri, "to_ref": r["from"]})
        testi.append({"ref": f"speech:{x['uri']}", "text": x["testo"], "hash": _h(x["testo"])})

    for sp in blocchi:
        punto = punto_di(sp)
        da = sp.find(AKN + "from")
        etichetta = re.sub(r"\s+", " ", "".join(da.itertext())).strip() if da is not None else ""
        href = persone.get((sp.get("by") or "").lstrip("#"))
        ruolo = ruoli.get((sp.get("as") or "").lstrip("#"))
        if etichetta.upper() == "PRESIDENTE" and href:
            presidente = (href, ruolo or "PRESIDENTE")
        elif not etichetta and sp.get("by") == "#p":         # blocco senza nome: il Presidente che continua a parlare
            etichetta, (href, ruolo) = "PRESIDENTE", presidente
        corrente = nuovo_intervento(punto, etichetta, href, ruolo)
        for j, p in enumerate(sp.findall(AKN + "p")):
            t, dids = _paragrafo(p)
            m = testa.match(t) if j else None
            chi = m.group(1).strip().upper() if m else None
            if chi and (chi == "PRESIDENTE" or chi in nomi):          # un altro oratore dentro lo stesso blocco
                chiudi(corrente)
                href2, ruolo2 = presidente if chi == "PRESIDENTE" else nomi[chi]
                corrente = nuovo_intervento(punto, m.group(1).strip(), href2, ruolo2)
                t = t[m.end():]
            g = GRUPPO.match(dids[0]) if dids else None
            if g and sigla(g.group(1)) and reazioni(dids[0])[0]["kind"] == "other" and not corrente["testo"]:
                corrente["gruppo"], dids = g.group(1), dids[1:]
            t = re.sub(r"^(?:[.,:]\s*)+", "", t).strip()                # «. (Il Presidente… in piedi). Onorevoli» -> «Onorevoli»
            inizio = len(corrente["testo"]) + (2 if corrente["testo"] else 0)
            if t:
                corrente["testo"] = f"{corrente['testo']}\n\n{t}" if corrente["testo"] else t
            corrente["reazioni"] += [(inizio, d) for d in dids]
        chiudi(corrente)
    return {"nodi": nodi, "archi": archi, "testi": testi}
