"""I documenti parlamentari (Doc.: DEF, proposte di modifica del Regolamento, relazioni delle Giunte…) fra gli atti.

Un atto per documento e ramo, solo per quelli di cui un dibattito o un voto del ramo parla: `it:camera:19:doc:LVII:1`.
Le schede vengono da dati.senato.it (osr:Documento con numeroRomano; le petizioni non ce l'hanno) e dati.camera.it
(ocd:DOC, solo una parte dei documenti discussi); il titolo che manca si ricava dal dibattito o dal voto.

Il passo gira dopo il caricamento, ogni notte, perché ricaricare una seduta riscrive `vote_act` e `agenda_item_act`:
- Senato: il voto indica già la scheda (`vote_act.act_ref`), qui si collega all'atto;
- Camera: la fonte non indica l'atto, si legge il documento nella descrizione del voto se il voto non ha altri atti.

Collega anche i voti ricaricati dopo il loro atto (act_ref già uguale a source_uri, act vuoto) e toglie le entità HTML rimaste nei testi dei voti e dei titoli dei dibattiti (`&amp;#39;`).
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from typing import NamedTuple

from .carica.postgres import _csv, leggi_csv, psql
from .fonti import camera_ocd
from .fonti.sparql import _richiesta, interroga
from .lago import Lago

FONTE = "documenti_parlamentari"
LEG = 19
ENDPOINT_SENATO = "https://dati.senato.it/sparql"
P_SENATO = "PREFIX osr:<http://dati.senato.it/osr/> "
Q_SENATO = {
    "documenti": P_SENATO + """SELECT ?d ?r ?num ?suff ?tipo ?titolo ?data WHERE { ?d a osr:Documento ; osr:legislatura {LEG} ; osr:numeroRomano ?r .
 OPTIONAL { ?d osr:numeroDoc ?num } OPTIONAL { ?d osr:suffissoNumeroDoc ?suff } OPTIONAL { ?d osr:tipoDoc ?tipo }
 OPTIONAL { ?d osr:titolo ?titolo } OPTIONAL { ?d osr:dataPresentazione ?data } }""",
    "testi": P_SENATO + "SELECT ?d ?url WHERE { ?d a osr:Documento ; osr:legislatura {LEG} ; osr:numeroRomano ?r ; osr:URLTesto ?url }",
}
Q_CAMERA = """SELECT ?d ?id ?title ?type ?date ?rel WHERE { ?d a ocd:DOC ; ocd:rif_leg <http://dati.camera.it/ocd/legislatura.rdf/repubblica_{LEG}> ; dc:identifier ?id .
 OPTIONAL { ?d dc:title ?title } OPTIONAL { ?d dc:type ?type } OPTIONAL { ?d dc:date ?date } OPTIONAL { ?d dc:relation ?rel } } ORDER BY ?d"""
PDF_CAMERA = "https://documenti.camera.it/_dati/leg{leg}/lavori/documentiparlamentari/IndiceETesti/{cat}/{num}/INTERO.pdf"

# ---------- i riferimenti nel testo: «Doc. IV-ter, n. 13-A», «(DOC. XVIII-BIS, n. 10)», «Doc. XXII, nn. 11-14-16», «Docc. LVII, n. 01-bis» ----------

LATINI = "bis|ter|quater|quinquies|sexies|septies|octies|novies|decies"
_SERIE = r"(?P<series>[IVXLCDM]+(?:-(?i:" + LATINI + r"))?)"
_TOKEN = r"\d+(?:\s*[-.]\s*(?i:" + LATINI + r")\b)?"
_NUMERI = r"(?P<nums>" + _TOKEN + r"(?:\s*(?:-|,|\be\b|\bed\b)\s*(?:[nN]{1,2}\.\s*)?" + _TOKEN + r")*)"
_RELAZIONE = r"(?:\s*-\s*(?P<report>A(?:/[IVXR]+)?)(?![a-zA-Z]))?"
_RIF = re.compile(_SERIE + r"\s*,?\s*(?:[nN]{1,2}\.?\s*)?" + _NUMERI + _RELAZIONE)
_PREFISSO = re.compile(r"(?i:\bdocc?\s*\.|\bdocument[oi]\b|\bdoc\b)\s*")
_SEGUE = re.compile(r"\s*,?\s*(?:\b(?:e|ed)\b\s*)?(?:(?i:del\s+)?(?i:docc?\.)\s*)?(?=[IVXLCDM]+(?:-|\s*,|\s+[nN]))")
_TOKEN_RE = re.compile(_TOKEN)
_SPAZI = re.compile(r"\s+")


class Rif(NamedTuple):
    serie: str
    numero: str
    relazione: str | None = None


def _serie(s: str) -> str:
    testa, _, coda = s.partition("-")
    return testa.upper() + (f"-{coda.lower()}" if coda else "")


def _numero(t: str) -> str:
    """«1.bis» -> «1-bis»; gli zeri restano: «01-bis» è un altro documento da «1-bis»."""
    m = re.match(r"(\d+)\s*(?:[-.]\s*([a-zA-Z]+))?$", t.strip())
    return (m.group(1) + (f"-{m.group(2).lower()}" if m.group(2) else "")) if m else t.strip()


def riferimenti(testo: str | None) -> list[Rif]:
    """Ogni documento che il testo nomina, in ordine e senza doppioni."""
    testo, fuori = testo or "", []
    for pre in _PREFISSO.finditer(testo):
        pos = pre.end()
        while m := _RIF.match(testo, pos):
            for t in _TOKEN_RE.findall(m.group("nums")):
                r = Rif(_serie(m.group("series")), _numero(t), m.group("report"))
                if r not in fuori:
                    fuori.append(r)
            pos = m.end()
            c = _SEGUE.match(testo, pos)
            if not c or c.end() == pos:
                break
            pos = c.end()
    return fuori


def chiavi(testo: str | None) -> list[tuple[str, str]]:
    """(serie, numero): la relazione della commissione («-A») è lo stesso documento."""
    return list(dict.fromkeys((r.serie, r.numero) for r in riferimenti(testo)))


def nome(k: tuple[str, str]) -> str:
    return f"Doc. {k[0]}, n. {k[1]}"


def pulisci(t: str | None) -> str | None:
    if not t:
        return None
    return _SPAZI.sub(" ", re.sub(r"<[^>]+>", " ", html.unescape(html.unescape(t)))).strip() or None


_PROCEDURA = re.compile(r"^(?:(?:seguito della |ripresa della )?discussione(?: congiunta)?(?: e approvazione)?(?: dalla sede redigente)?|esame|si riprende la discussione)\s+"
                       r"(?:(?:del|della|dello|dei|delle|degli)\s+)?(?:(?:documento|documenti)\s*:)?\s*", re.I)
_NON_TITOLO = re.compile(r"^(?:emendament|articol|identici|subemendament|ordine del giorno|odg|votazione|risoluzione|mozione|audizion|dichiarazioni)", re.I)
# «Presentato dal Presidente del Consiglio dei ministri: MELONI», «D'iniziativa dei deputati: BICCHIELLI ed altri»: chi presenta, non il titolo
_PRESENTATORE = re.compile(r"\s*(?:Presentat[oa] dal(?:la|l')?\s.*?|D'iniziativa de(?:i|l|lla) deputat[oaie]+):\s*[A-ZÀ-Ý'][A-ZÀ-Ý']+(?:\s+[A-ZÀ-Ý'][A-ZÀ-Ý']+)*(?:\s+ed altri)?(?=\s|\(|$)")
_RELATORE = re.compile(r"\s*\(Relat(?:ore|rice)[^)]*\)")
# un titolo che dice solo un periodo, un volume o una persona, o comincia in maiuscolo
_DEBOLE = re.compile(r"^(?:(?i:anno\b|periodo\b|volume\b|allegat|relat|n\.\s*\d|annesso|di una domanda|del dott|del sen|dell'on)|[a-zà-ý]|[A-ZÀ-Ý]{3,}\s+[A-ZÀ-Ý]{2,}\b)")
# i documenti del Governo che arrivano ai due rami con la stessa serie e lo stesso numero
SERIE_GOVERNO = {"LVII", "CCXL", "CCXLIV", "CCXXXII", "CCXXXIII", "LXXXVI", "LXXXVII"}


def titolo_scheda(titolo: str | None) -> str | None:
    """Il titolo della scheda della Camera senza chi presenta; niente se dice solo un periodo o una persona."""
    t = pulisci(titolo)
    if not t:
        return None
    t = _RELATORE.sub("", _PRESENTATORE.sub(" ", t))
    t = re.sub(r"^\s*Presentat[oa] dal(?:la|l')?\s+[A-ZÀ-Ý' ]+?\s*\((.*)\)\s*$", r"\1", t)
    t = _SPAZI.sub(" ", t).strip(" -")
    return t if len(t) >= 15 and not _DEBOLE.match(t) else None


def titolo_prima(testo: str | None, k: tuple[str, str]) -> str | None:
    """Cosa dice il dibattito del documento, prima del riferimento: «Conto consuntivo … (Doc. VIII, n. 1); Progetto … (Doc. VIII, n. 2)»."""
    t = pulisci(testo)
    for m in re.finditer(r"\(\s*(?i:docc?)\.", t or ""):
        fine = t.find(")", m.start())
        if k not in chiavi(t[m.start():fine + 1 if fine > 0 else None]):
            continue
        testa = _PROCEDURA.sub("", re.split(r"[;:]\s", t[:m.start()])[-1].strip()).strip(" ,.-")
        testa = re.sub(r"^di una (?=domanda|richiesta)", "", testa, flags=re.I)
        return testa[0].upper() + testa[1:] if len(testa) >= 15 and not _NON_TITOLO.match(testa) else None
    return None


def pdf_camera(k: tuple[str, str]) -> str | None:
    """Il testo nell'archivio della Camera: «IV-ter» è 004ter, «1-bis» è 001bis."""
    valori = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    testa, _, latino = k[0].partition("-")
    m = re.fullmatch(r"(\d+)(?:-([a-z]+))?", k[1])
    if not m or not testa:
        return None
    v = [valori[c] for c in testa]
    romano = sum(-x if i + 1 < len(v) and x < v[i + 1] else x for i, x in enumerate(v))
    return PDF_CAMERA.format(leg=LEG, cat=f"{romano:03d}{latino}", num=f"{int(m.group(1)):03d}{m.group(2) or ''}")


def data_iso(v: str | None) -> str | None:
    d = re.sub(r"\D", "", (v or "")[:10])
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else None


# ---------- le fonti: si salvano nel lago, e se l'endpoint non risponde vale l'ultima copia ----------

def _scarica(ctx, chiave: str, leggi, endpoint: str) -> list[dict]:
    lago = Lago(ctx.cartella)
    try:
        righe = leggi()
        if not righe:
            raise RuntimeError("nessuna riga")
        righe.sort(key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
        lago.salva(FONTE, chiave, json.dumps(righe, ensure_ascii=False, indent=0).encode("utf-8"), endpoint, "json")
        return righe
    except Exception as e:                              # senato.it blocca spesso: si va avanti con la copia precedente
        u = lago.ultimo(FONTE, chiave)
        if not u:
            raise
        ctx.log(f"{chiave}: {str(e)[:120]}; uso la copia precedente")
        return json.loads(lago.leggi(u["file"]))


def schede_senato(documenti: list[dict], testi: list[dict]) -> tuple[dict, dict]:
    """(serie, numero) -> scheda; e ogni uri delle schede -> (serie, numero)."""
    per_testo = defaultdict(list)
    for r in testi:
        per_testo[r["d"]].append(r["url"])
    gruppi = defaultdict(list)
    for r in documenti:
        if not r.get("num"):
            continue
        grezzo = r["num"] + (f"-{r['suff']}" if r.get("suff") else "")
        token = re.match(r"\d+(?:-(?:" + LATINI + r"))?", grezzo, re.I)
        k = (_serie(r["r"].replace(" ", "-")), _numero(token.group(0) if token else grezzo))
        gruppi[k].append({"uri": r["d"], "titolo": pulisci(r.get("titolo")), "tipo": pulisci(r.get("tipo")), "data": data_iso(r.get("data")),
                          "testi": per_testo.get(r["d"], []), "piena": bool(token) and token.group(0) == grezzo})   # «bis - Integrazione» è un'aggiunta
    schede, uri = {}, {}
    for k, rs in gruppi.items():
        rs.sort(key=lambda x: (not x["piena"], x["data"] or "", x["uri"]))
        schede[k] = {**rs[0], "testi": list(dict.fromkeys(u for x in rs for u in x["testi"]))}
        uri.update({x["uri"]: k for x in rs})
    return schede, uri


def schede_camera(righe: list[dict]) -> dict:
    """(serie, numero) -> scheda del testo (identificativo senza suffisso, uri senza numero di foglio), con i link di tutti i fogli."""
    fuori: dict = defaultdict(lambda: {"uri": None, "titolo": None, "tipo": None, "data": None, "testi": []})
    per_uri = {}
    for r in righe:
        x = per_uri.setdefault(r["d"], {**r, "rels": []})
        if r.get("rel"):
            x["rels"].append(r["rel"])
    for x in sorted(per_uri.values(), key=lambda r: r["d"]):
        if re.search(r"[A-Z]{2,}$", x["id"].split(",n.")[-1]):         # doc19_LVIIn1BIS è citato altrove come 01-bis: numero non affidabile
            continue
        for rif in riferimenti(x["id"]):
            s = fuori[(rif.serie, rif.numero)]
            s["testi"] += [u for u in x["rels"] if u not in s["testi"]]
            semplice = rif.relazione is None and not re.search(r"_\d+$", x["d"]) and re.fullmatch(r"Doc\.[^,]+,n\.[\w-]+", x["id"].replace(" ", ""))
            if semplice and not s["uri"]:
                s.update(uri=x["d"], titolo=pulisci(x.get("title")), tipo=pulisci(x.get("type")), data=data_iso(x.get("date")))
    return fuori


# ---------- il passo ----------

def _piu_frequente(voci: list[str]) -> str | None:
    return Counter(voci).most_common(1)[0][0] if voci else None


def passo(ctx) -> dict:
    sen_d = _scarica(ctx, f"leg{LEG}-senato-documenti", lambda: _richiesta(ENDPOINT_SENATO, Q_SENATO["documenti"].replace("{LEG}", str(LEG)), 2), ENDPOINT_SENATO)
    sen_t = _scarica(ctx, f"leg{LEG}-senato-documenti-testi", lambda: _richiesta(ENDPOINT_SENATO, Q_SENATO["testi"].replace("{LEG}", str(LEG)), 2), ENDPOINT_SENATO)
    cam = _scarica(ctx, f"leg{LEG}-camera-documenti", lambda: interroga(camera_ocd.ENDPOINT, camera_ocd.PREFISSI + Q_CAMERA.replace("{LEG}", str(LEG))), camera_ocd.ENDPOINT)
    senato, uri_senato = schede_senato(sen_d, sen_t)
    camera = schede_camera(cam)

    # di quali documenti parlano i dibattiti e i voti
    voluti = {"camera": set(), "senato": set()}
    titoli = defaultdict(list)
    item_doc = []                                   # (ramo, item, act_ref, chiavi)
    for item, rif, ramo, titolo in leggi_csv("""SELECT x.item, x.act_ref, s.chamber, a.title FROM agenda_item_act x JOIN agenda_item a ON a.uri = x.item
            JOIN sitting s ON s.uri = a.sitting WHERE x.act_ref LIKE 'doc:%' AND s.chamber IN ('camera', 'senato')"""):
        ks = chiavi("Doc. " + rif[4:])
        if ks:
            voluti[ramo].update(ks)
            item_doc.append((ramo, item, rif, ks))
            for k in ks:
                if t := titolo_prima(titolo, k):
                    titoli[(ramo, k)].append(t)
    # Senato: la scheda indicata dal voto. Camera: il documento nominato, se il voto non ha altri atti
    voti_senato = 0
    for (rif,) in leggi_csv("SELECT DISTINCT act_ref FROM vote_act WHERE act_ref LIKE 'http://dati.senato.it/documento/%'"):
        if rif in uri_senato:
            voluti["senato"].add(uri_senato[rif])
            voti_senato += 1
    voti_camera = []
    for v, titolo, descr in leggi_csv(f"""SELECT v.uri, v.title, v.description FROM vote v WHERE v.chamber = 'camera' AND v.legislature = {LEG}
            AND (v.description ~* 'doc' OR v.title ~* 'doc')
            AND NOT EXISTS (SELECT 1 FROM vote_act a WHERE a.vote = v.uri AND a.act IS NOT NULL AND a.act NOT LIKE '%:doc:%')"""):
        ks = chiavi(descr) or chiavi(titolo)
        if ks:
            voluti["camera"].update(ks)
            voti_camera += [(v, k) for k in ks]
            for k in ks:
                if t := titolo_prima(descr, k):
                    titoli[("camera", k)].append(t)

    uri_doc = lambda ramo, k: f"it:{ramo}:{LEG}:doc:{k[0]}:{k[1]}"  # noqa: E731
    righe, senza_titolo = [], 0
    for ramo, ks in voluti.items():
        for k in sorted(ks):
            propria = (senato if ramo == "senato" else camera).get(k) or {}
            altra = senato.get(k) or {}
            del_governo = altra.get("titolo") if k[0] in SERIE_GOVERNO else None
            titolo = (propria.get("titolo") if ramo == "senato" else del_governo or titolo_scheda(propria.get("titolo"))) \
                or _piu_frequente(titoli[(ramo, k)]) or propria.get("tipo")
            senza_titolo += not titolo
            testi = propria.get("testi") or []
            scheda = testi[0] if testi else pdf_camera(k) if ramo == "camera" else None
            righe.append([uri_doc(ramo, k), ramo, LEG, nome(k), "document", propria.get("tipo"), titolo or nome(k), propria.get("data") or altra.get("data"),
                          scheda, "{" + ",".join(json.dumps(u) for u in testi) + "}" if testi else None, FONTE, propria.get("uri")])
    voti_c = [[v, f"doc:{k[0]}:{k[1]}", uri_doc("camera", k)] for v, k in voti_camera]
    mappa_s = [[u, uri_doc("senato", k)] for u, k in uri_senato.items() if k in voluti["senato"]]
    item_1, item_2 = [], []
    for ramo, item, rif, ks in item_doc:
        item_1.append([item, rif, uri_doc(ramo, ks[0])])
        item_2 += [[item, nome(k), uri_doc(ramo, k)] for k in ks[1:]]

    entita = "replace(replace(replace(replace(replace({c}, '&amp;', '&'), '&#39;', ''''), '&quot;', '\"'), '&#8221;', '”'), '&#8220;', '“')"
    filtro = "{c} ~ '&(amp|#39|quot|#822[01]);'"
    psql(f"""BEGIN;
CREATE TEMP TABLE d (uri text, chamber text, legislature int, number text, kind text, kind_raw text, title text, date date, card_url text, text_urls text[], source text, source_uri text) ON COMMIT DROP;
COPY d FROM STDIN WITH (FORMAT csv);
{_csv(righe)}\\.
INSERT INTO act (uri, chamber, legislature, number, kind, kind_raw, title, date, card_url, text_urls, source, source_uri)
  SELECT * FROM d ON CONFLICT (uri) DO UPDATE SET number = excluded.number, kind_raw = excluded.kind_raw, title = excluded.title, date = excluded.date,
    card_url = excluded.card_url, text_urls = excluded.text_urls, source_uri = excluded.source_uri;
CREATE TEMP TABLE ms (ref text, uri text) ON COMMIT DROP;
COPY ms FROM STDIN WITH (FORMAT csv);
{_csv(mappa_s)}\\.
UPDATE vote_act v SET act = m.uri FROM ms m WHERE v.act_ref = m.ref AND v.act IS DISTINCT FROM m.uri;
UPDATE vote_act v SET act = a.uri FROM act a, vote x WHERE x.uri = v.vote AND v.act IS NULL AND a.chamber = x.chamber AND a.source_uri = v.act_ref;
CREATE TEMP TABLE vc (vote text, act_ref text, act text) ON COMMIT DROP;
COPY vc FROM STDIN WITH (FORMAT csv);
{_csv(voti_c)}\\.
INSERT INTO vote_act (vote, act_ref, act) SELECT * FROM vc ON CONFLICT (vote, act_ref) DO UPDATE SET act = excluded.act;
CREATE TEMP TABLE i1 (item text, act_ref text, act text) ON COMMIT DROP;
COPY i1 FROM STDIN WITH (FORMAT csv);
{_csv(item_1)}\\.
UPDATE agenda_item_act x SET act = i.act FROM i1 i WHERE x.item = i.item AND x.act_ref = i.act_ref AND x.act IS DISTINCT FROM i.act;
CREATE TEMP TABLE i2 (item text, act_ref text, act text) ON COMMIT DROP;
COPY i2 FROM STDIN WITH (FORMAT csv);
{_csv(item_2)}\\.
INSERT INTO agenda_item_act (item, act_ref, act) SELECT * FROM i2 ON CONFLICT (item, act_ref) DO UPDATE SET act = excluded.act;
UPDATE vote SET description = {entita.format(c='description')} WHERE {filtro.format(c='description')};
UPDATE agenda_item SET title = {entita.format(c='title')} WHERE {filtro.format(c='title')};
COMMIT;
""")
    fuori = {"documenti": len(righe), "camera": len(voluti["camera"]), "senato": len(voluti["senato"]), "senza_titolo": senza_titolo,
             "voti_camera": len(voti_c), "schede_senato_votate": voti_senato}
    ctx.log(f"{FONTE}: {fuori}")
    return fuori
