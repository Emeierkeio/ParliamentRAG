"""Dal resoconto stenografico XML della Camera ai record dello schema v3.

Trasformazione pura: stesso XML, stessi record. Produce:
- `Sitting`, `AgendaItem`, `Speech`, `Segment` (paragrafi), `Reaction` per il grafo;
- `testo` per Postgres: il testo canonico di ogni intervento e di ogni paragrafo, più il markup originale.

Il testo canonico è il parlato senza didascalie. Le didascalie («(Applausi dei deputati del gruppo
FdI)») diventano `Reaction` con la posizione nel testo canonico, quindi niente va perso.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

# Didascalia: corsivo fra parentesi. Più reazioni nella stessa parentesi sono separate da « - » (Camera) o da «. » (Senato).
TIPI = [("applausi ironici", "ironic_applause"), ("applausi", "applause"), ("vive proteste", "protests"), ("proteste", "protests"),
        ("vivaci commenti", "comments"), ("commenti", "comments"), ("si ride", "laughter"), ("ilarità", "laughter"), ("interruzione", "interruption"),
        ("una voce", "interruption"), ("voci", "interruption"), ("rumori", "noise"), ("brusio", "noise"), ("brusìo", "noise"),
        ("scambio di apostrofi", "altercation"), ("il deputato", "action"), ("la deputata", "action"), ("i deputati", "action"),
        ("deputati del gruppo", "action"), ("il senatore", "action"), ("la senatrice", "action"), ("i senatori", "action")]
# note del resoconto che non sono reazioni dell'Aula
PROCEDURA = re.compile(r"^(segue|vedi|v\. |ulteriori comunicazioni|la seduta|i lavori|il testo|la votazione|così rimane|cfr\.)", re.I)
SEPARA = re.compile(r"\s+[-–]\s+|(?<=[a-zà-ÿ]{3})\.\s+(?=[A-ZÀ-Ý])")
# chi reagisce: «dei deputati dei gruppi X e Y e di deputati del gruppo Z» -> una parte per soggetto
PARTI = re.compile(r",?\s+e\s+(?=(?:di|dei|del|della|delle|degli|dal|dai)\s)|,\s+(?=(?:di|dei|del|della|dal|dai)\s)")
PREP = re.compile(r"^(?:(?:dai banchi|da parte)\s+(?:del|dei|della)\s+|(?:di|dei|del|della|delle|degli|dal|dai|da|i|gli|le|il|la)\s+)", re.I)
IN_PIEDI = re.compile(r"\s+si\s+lev(?:a|ano)\s+in\s+piedi.*$", re.I)
GRUPPO_DI = re.compile(r"^(?:(?:deputat[aeio]|senator[ei]|senatric[ei]|componenti|parlamentari)\s+(?:(?:del|dei|della|delle)\s+)?)?"
                       r"(?:gruppo|gruppi|componente|componenti)\s+(?P<nome>.+)$", re.I)
PERSONA = re.compile(r"^(?:deputat[oa]|senatore|senatrice|onorevole|deputati|deputate|senatori|senatrici)\s+(?P<nomi>[A-ZÀ-Ý].+)$")
GRUPPO_SENZA = re.compile(r"-|\b(?:Partito|MoVimento|Movimento|Fratelli|Lega|Forza Italia|Alleanza|Azione|Italia Viva|Noi Moderati|Misto)\b")
# la sigla dopo il nome, con al più una parentesi dentro: «(M5S)», «(NM(N-C-U-I)-M)»
SIGLA = re.compile(r"\s*\(((?:[^()]|\([^()]{1,40}\)){1,60})\)")
CARICA = re.compile(r"^(?:(?:vice\s*)?ministr[oa]|sottosegretari[oa]|presidente del consiglio|rappresentant[ei] del governo|governo)\b", re.I)


def chi_reagisce(p: str) -> list[dict]:
    """«Applausi dei deputati dei gruppi PD-IDP e AVS e di deputati del gruppo M5S» -> [gruppi «PD-IDP e AVS», gruppo «M5S»];
    «Commenti dei deputati Fornaro e Casu» -> due persone; «Commenti del Ministro Bernini» -> carica. I nomi dei gruppi
    restano come li scrive il resoconto: li lega ai gruppi il caricamento, per data (un elenco «X, Y e Z» non si divide
    qui perché «e» sta anche dentro i nomi, come «Alleanza Verdi e Sinistra»)."""
    resto = re.sub(r",\s+che\b.*$", "", IN_PIEDI.sub("", p)).strip()          # «del gruppo M5S, che si alzano»
    basso = resto.lower()
    chiave = next((k for k, _ in TIPI if basso.startswith(k)), "")
    if chiave and not chiave.startswith(("il ", "la ", "i ", "deputati")):     # «Applausi», «Commenti»: via la parola della reazione
        resto = resto[len(chiave):].strip()
    out = []
    for parte in PARTI.split(resto):
        x = parte.strip(" ,.")
        while PREP.match(x):
            x = PREP.sub("", x, count=1)
        if not x:
            continue
        if x.lower() == "presidente":
            out.append({"kind": "chair", "name": "Presidente"})
        elif CARICA.match(x):
            out.append({"kind": "office", "name": x})
        elif m := GRUPPO_DI.match(x):
            out.append({"kind": "group", "name": m.group("nome").strip()})
        elif (m := PERSONA.match(x)) and not GRUPPO_SENZA.search(m.group("nomi")):
            for n in re.split(r"\s+e\s+|,\s+", m.group("nomi")):
                nome = re.match(r"(?:[A-ZÀ-Ý][\w'’]*(?:\s+|$))+", n.strip())       # «Gribaudo mostra un libro» -> «Gribaudo»
                if nome:
                    out.append({"kind": "person", "name": nome.group(0).strip()})
        elif m:                                                    # «dei deputati Partito Democratico-…»: manca «del gruppo»
            out.append({"kind": "group", "name": m.group("nomi")})
        elif re.match(r"^(?:deputati|deputate|senatori|senatrici)\s+", x, re.I):       # «di deputati del Partito Democratico-…»
            out.append({"kind": "group", "name": re.sub(r"^\S+\s+(?:(?:di|del|dei|della)\s+)?", "", x)})
        elif x[0].isupper():                                                           # «Applausi Partito Democratico-…»
            out.append({"kind": "group", "name": x})
    return out


def _h(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def _testo(el: ET.Element) -> tuple[str, list[dict]]:
    """Testo canonico di un elemento (senza nominativo e didascalie) e didascalie con la loro posizione."""
    parti: list[str] = []
    didascalie: list[dict] = []

    def visita(e: ET.Element, dentro_nominativo=False):
        if e.tag == "nominativo":
            if e.tail:
                parti.append(e.tail)
            return
        corsivo = e.tag == "emphasis" and e.get("type") == "italic"
        tutto = "".join(e.itertext()).strip()
        if corsivo and tutto.startswith("(") and tutto.endswith(")"):
            didascalie.append({"offset": len("".join(parti)), "raw": tutto})
        else:
            if e.text:
                parti.append(e.text)
            for f in e:
                visita(f)
        if e.tail and e is not el:
            parti.append(e.tail)

    if el.text:
        parti.append(el.text)
    for f in el:
        visita(f)
    testo = re.sub(r"[ \t\r\n]+", " ", "".join(parti)).strip()
    # le posizioni vanno ricalcolate sul testo con gli spazi normalizzati
    norm = []
    for d in didascalie:
        prima = re.sub(r"[ \t\r\n]+", " ", "".join(parti)[: d["offset"]]).lstrip()
        norm.append({**d, "offset": min(len(prima), len(testo))})
    return testo, norm


def reazioni(raw: str) -> list[dict]:
    """«(Applausi dei deputati del gruppo FdI - Proteste di deputati del gruppo PD)» → due reazioni; «(Applausi. Commenti)» del
    Senato → due reazioni."""
    interno = raw.strip()[1:-1]
    out = []
    for pezzo in SEPARA.split(interno):
        p = pezzo.strip().rstrip(".")
        if not p:
            continue
        basso = p.lower()
        tipo = "procedure" if PROCEDURA.match(p) else next((t for k, t in TIPI if basso.startswith(k)), "other")
        chi = chi_reagisce(p) if tipo not in ("procedure", "other") else []
        out.append({"kind": tipo, "text": p, "from": "; ".join(x["name"] for x in chi) or None, "parts": chi})
    return out


def trasforma(xml: bytes, fonte: dict) -> dict:
    """Restituisce {'nodi': [...], 'archi': [...], 'testi': [...]} per una seduta."""
    radice = ET.fromstring(xml)
    sed = radice if radice.tag == "seduta" else radice.find(".//seduta")
    leg, num = int(sed.get("legislatura")), int(sed.get("numero"))
    data = f"{sed.get('anno')}-{sed.get('mese')}-{sed.get('giorno')}"
    s_uri = f"it:camera:{leg}:sed{num:04d}"
    nodi, archi, testi = [], [], []
    nodi.append({"label": "Sitting", "uri": s_uri, "chamber": "camera", "body": f"it:camera:{leg}:aula", "number": num, "date": data,
                 "status": "held", "kind": "assembly_verbatim", "source": "camera_xml", "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")})
    atti_per_dib = {}
    for a in sed.iter("argomento"):
        atti_per_dib[a.get("idDibattito")] = [f"{x.get('tipologiaAtto')}:{x.get('codiceArgomento')}" for x in a.iter("atto")]
    ordine_dib = 0
    for dib in sed.iter("dibattito"):
        ordine_dib += 1
        d_id = dib.get("id")
        titolo = re.sub(r"\s+", " ", "".join((dib.find("titolo").itertext() if dib.find("titolo") is not None else []))).strip()
        i_uri = f"{s_uri}:{d_id}"
        nodi.append({"label": "AgendaItem", "uri": i_uri, "order": ordine_dib, "title": titolo})
        archi.append({"type": "HAS_ITEM", "from": s_uri, "to": i_uri, "order": ordine_dib})
        for ref in atti_per_dib.get(d_id, []):
            archi.append({"type": "ABOUT", "from": i_uri, "to_ref": ref})
        ordine_int = 0
        for inter in dib.iter("intervento"):
            ordine_int += 1
            sp_uri = f"{s_uri}:{inter.get('id')}"
            nom = inter.find(".//nominativo")
            corpo = inter.find("testoXHTML")
            # gruppo dichiarato nel resoconto: «RICCARDO RICCIARDI (M5S). Grazie…», anche «(NM(N-C-U-I)M-CP)»
            gruppo = None
            if nom is not None and nom.tail:
                m = SIGLA.match(nom.tail)
                gruppo = m.group(1) if m else None
            paragrafi = [x for x in [corpo] if x is not None] + list(inter.findall("interventoVirtuale"))
            testo_tot, offset_par, ord_seg = "", 0, 0
            for par in paragrafi:
                t, dids = _testo(par)
                if par is corpo and gruppo:
                    t = re.sub(r"^\(\s*" + re.escape(gruppo) + r"\s*\)\.?\s*", "", t)
                elif par is corpo:
                    t = re.sub(r"^\.\s*", "", t)
                if not t and not dids:
                    continue
                ord_seg += 1
                inizio = len(testo_tot) + (2 if testo_tot else 0)
                testo_tot = f"{testo_tot}\n\n{t}" if testo_tot else t
                seg_uri = f"{sp_uri}:p{ord_seg}"
                nodi.append({"label": "Segment", "uri": seg_uri, "start": inizio, "end": inizio + len(t), "kind": "talk", "hash": _h(t)})
                archi.append({"type": "HAS_SEGMENT", "from": sp_uri, "to": seg_uri, "order": ord_seg})
                for k, d in enumerate(dids):
                    for j, r in enumerate(reazioni(d["raw"])):
                        r_uri = f"{sp_uri}:r{ord_seg}.{k + 1}.{j + 1}"
                        nodi.append({"label": "Reaction", "uri": r_uri, "kind": r["kind"], "offset": inizio + d["offset"], "raw": r["text"]})
                        archi.append({"type": "DURING", "from": r_uri, "to": sp_uri})
                        if r["from"]:
                            archi.append({"type": "FROM", "from": r_uri, "to_ref": r["from"], "parts": r["parts"]})
                offset_par = inizio
            nodi.append({"label": "Speech", "uri": sp_uri, "order": ordine_int, "hash": _h(testo_tot), "text_ref": f"speech:{sp_uri}",
                         "speaker_label": (nom.text or "").strip() if nom is not None else None,
                         "declared_group": gruppo, "anchor": inter.get("id")})
            archi.append({"type": "HAS_SPEECH", "from": i_uri, "to": sp_uri, "order": ordine_int})
            if nom is not None and nom.get("id"):
                archi.append({"type": "BY", "from": sp_uri, "to": f"it:person:camera:{nom.get('id')}", "as_group": gruppo,
                              "as_office": (nom.text or "").strip() if (nom.text or "").strip().isupper() and " " not in (nom.text or "").strip() else None})
            testi.append({"ref": f"speech:{sp_uri}", "text": testo_tot, "hash": _h(testo_tot),
                          "markup": ET.tostring(inter, encoding="unicode")})
    return {"nodi": nodi, "archi": archi, "testi": testi}
