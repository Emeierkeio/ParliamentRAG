"""Dal comunicato del Bollettino (HTML) ai record dello schema v3 per una commissione in un giorno.

- `Sitting` per ogni sede (sede referente, consultiva, audizioni, ufficio di presidenza…): chi presiede, orari,
  chi del governo interviene;
- `AgendaItem` per ogni argomento, con l'atto (C. 3001, Atto n. 439, Doc. …) e la fase («Seguito dell'esame e
  conclusione – Parere favorevole»);
- `Speech` di tipo `summary` per ogni paragrafo, con la persona, il gruppo e il ruolo quando il paragrafo è un
  intervento. È il riassunto degli uffici: non va citato tra virgolette come parola del deputato;
- `Document` per ogni allegato (proposte di parere, emendamenti, risoluzioni).

Trasformazione pura, con html.parser della libreria standard.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser

ORARIO = re.compile(r"(comincia|termina|inizia)\D+(\d{1,2}(?:[.,]\d{2})?)", re.I)
# la sigla di un gruppo, con al più una parentesi dentro: «(FDI)», «(NM(N-C-U-I)M-CP)»
SIGLA = re.compile(r"\(((?:[^()]|\([^()]{1,40}\)){1,60})\)")
ATTI = [(re.compile(r"\bC\. (\d+[\w-]*)"), "ac"), (re.compile(r"\bAtto n\. (\d+)"), "ag"),
        (re.compile(r"\bDoc\. ([IVXLC]+(?:-\w+)?(?:,)? n\. \d+)"), "doc"), (re.compile(r"\b([1-7]-\d{5})\b"), "aic")]


def _sigla(g: str | None) -> str | None:
    """«(NM(N-C-U-I)M-CP)» -> «NM(N-C-U-I)M-CP»: via solo la coppia di parentesi esterna."""
    m = SIGLA.fullmatch(_spazi(g or ""))
    return m.group(1).strip() if m else (_spazi(g or "").strip("()") or None)


def _h(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


def _spazi(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


class _Lettore(HTMLParser):
    """Raccoglie i paragrafi del corpo con classe, id, title, testo, persone collegate, gruppo e corsivi."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.campi: dict[str, list[str]] = {}       # intestazione degli stenografici: commissione, comitato, riferimenti
        self._campo: str | None = None
        self.intestazione: list[str] = []
        self.paragrafi: list[dict] = []
        self.sede: str | None = None
        self.p: dict | None = None
        self.dentro = {"intestazione": False, "centro": False, "a_persona": None, "gruppo": False, "em": 0, "strong": 0, "pagina": 0}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag == "meta" and a.get("name"):
            self.meta[a["name"]] = a.get("content") or ""
        elif tag == "div" and a.get("id") == "intestazione":
            self.dentro["intestazione"] = True
        elif tag == "div" and a.get("id") == "corpo":
            self.dentro["intestazione"] = False
        elif tag == "div" and cls in ("commissioneNumero", "comitatoDescrizione", "stenograficoRiferimenti"):
            self._campo = cls
            self.campi.setdefault(cls, []).append("")
        elif tag == "div" and "centerBold" in cls and self.dentro["intestazione"]:
            self.dentro["centro"] = True
            self.intestazione.append("")
        elif tag == "div" and "sede" in cls.split():
            self.sede = a.get("id")
        elif tag == "div" and "allegato" in cls:
            self.sede = a.get("id") or self.sede
        elif tag == "span" and "numeroPagina" in cls:
            self.dentro["pagina"] += 1
        elif tag == "p":
            self.p = {"class": cls, "id": a.get("id"), "title": a.get("title"), "sede": self.sede, "testo": "", "persone": [],
                      "gruppo": None, "corsivi": [], "grassetti": [], "fine_primo": None}
        elif self.p is not None:
            href = a.get("href") or ""
            if tag == "a" and cls == "gruppo":
                # solo il gruppo subito dopo il nome di chi parla: gli altri sono dei deputati citati
                f = self.p["fine_primo"]
                self.dentro["gruppo"] = self.p["gruppo"] is None and f is not None and not self.p["testo"][f:].strip()
            elif tag == "a" and ("linkSchedaDeputato" in cls or "idPersona=" in href
                                 or (not href and "intervento" in self.p["class"] and not self.p["persone"])):
                # deputato (link alla scheda) o, negli stenografici, audito (link senza indirizzo)
                m = re.search(r"idPersona=(\d+)", href)
                self.dentro["a_persona"] = m.group(1) if m else ""
                self.p["persone"].append([m.group(1) if m else None, ""])
            elif tag == "em":
                self.dentro["em"] += 1
                self.p["corsivi"].append("")
            elif tag == "strong":
                self.dentro["strong"] += 1
                self.p["grassetti"].append("")
            elif tag == "br":
                self.p["testo"] += "\n"

    def handle_endtag(self, tag):
        if tag == "div" and self._campo:
            self._campo = None
        if tag == "div" and self.dentro["centro"]:
            self.dentro["centro"] = False
        elif tag == "span" and self.dentro["pagina"]:
            self.dentro["pagina"] -= 1
        elif tag == "p" and self.p is not None:
            self.paragrafi.append(self.p)
            self.p = None
        elif self.p is not None:
            if tag == "a":
                if self.dentro["a_persona"] is not None and len(self.p["persone"]) == 1:
                    self.p["fine_primo"] = len(self.p["testo"])
                self.dentro["a_persona"] = None
                self.dentro["gruppo"] = False
            elif tag == "em" and self.dentro["em"]:
                self.dentro["em"] -= 1
            elif tag == "strong" and self.dentro["strong"]:
                self.dentro["strong"] -= 1

    def handle_data(self, data):
        if self.dentro["pagina"]:
            return  # «Pag. 21» del cartaceo dentro il testo
        if self.dentro["centro"] and self.intestazione:
            self.intestazione[-1] += data
        if self._campo:
            self.campi[self._campo][-1] += data
        if self.p is None:
            return
        self.p["testo"] += data
        if self.dentro["a_persona"] is not None and self.p["persone"]:  # "" = audito senza scheda
            self.p["persone"][-1][1] += data
        if self.dentro["gruppo"]:
            self.p["gruppo"] = (self.p["gruppo"] or "") + data
        if self.dentro["em"] and self.p["corsivi"]:
            self.p["corsivi"][-1] += data
        if self.dentro["strong"] and self.p["grassetti"]:
            self.p["grassetti"][-1] += data


def leggi(html: bytes) -> _Lettore:
    l = _Lettore()
    l.feed(html.decode("utf-8-sig", errors="replace"))
    l.close()
    return l


def atti(testo: str) -> list[str]:
    """«C. 3001 Governo» -> ['ac:3001']; «Atto n. 439» -> ['ag:439']; «5-04321» -> ['aic:5-04321']."""
    out = []
    for rx, tipo in ATTI:
        out += [f"{tipo}:{_spazi(m.group(1))}" for m in rx.finditer(testo)]
    return list(dict.fromkeys(out))


def _fase(corsivo: str | None) -> str | None:
    """«(Seguito dell'esame e conclusione – Parere favorevole).» -> «Seguito dell'esame e conclusione – Parere favorevole»."""
    m = re.match(r"^\((.*)\)\W*$", _spazi(corsivo or ""))
    return m.group(1).strip() if m else None


def _ore(h: str) -> str:
    h = h.replace(",", ".")
    return f"{int(h.split('.')[0]):02d}:{h.split('.')[1] if '.' in h else '00'}"


def _orario(testo: str) -> str | None:
    m = ORARIO.search(testo)
    if not m:
        return None
    h = m.group(2).replace(",", ".")
    return f"{int(h.split('.')[0]):02d}:{h.split('.')[1] if '.' in h else '00'}"


def trasforma(comunicato: bytes, allegati: bytes | None, fonte: dict, leg: int = 19) -> dict:
    l = leggi(comunicato)
    giorno = l.meta.get("date", "")
    data = f"{giorno[:4]}-{giorno[4:6]}-{giorno[6:]}"
    codice = (l.meta.get("commissione") or "").replace("commissione.", "")
    titoli = [_spazi(x) for x in l.intestazione if _spazi(x)]
    nome_organo = next((t for t in titoli[titoli.index("COMUNICATO") - 1:titoli.index("COMUNICATO")] if "COMUNICATO" in titoli), None) \
        if "COMUNICATO" in titoli else None
    base = f"it:camera:{leg}:bol{giorno}:c{codice}"
    nodi, archi, testi = [], [], []
    sedute: dict[str, dict] = {}
    punto: dict | None = None
    ordini = {"punto": 0, "par": 0}
    uri_punti: set[str] = set()
    for p in l.paragrafi:
        if not p["sede"] or ".allegati." in (p["sede"] or ""):
            continue
        sid = p["sede"].rsplit(".", 1)[-1]                       # sede00020
        s_uri = f"{base}:{sid}"
        s = sedute.get(s_uri)
        if s is None:
            s = sedute[s_uri] = {"label": "Sitting", "uri": s_uri, "chamber": "camera", "body_code": codice, "body_name": nome_organo,
                                 "number": int(re.sub(r"\D", "", sid) or 0), "date": data, "status": "held", "kind": "committee_summary",
                                 "bulletin_number": int(l.meta.get("bollettino.numero") or 0) or None, "provisional": l.meta.get("bozza") == "true",
                                 "source": "camera_bollettino", "source_key": fonte.get("chiave"), "source_hash": fonte.get("impronta")}
            nodi.append(s)
            punto, ordini["punto"], ordini["par"] = None, 0, 0
        testo = _spazi(p["testo"])
        cls = p["class"].split()
        if "sede" in cls:
            s["seat"] = testo                                       # SEDE REFERENTE, AUDIZIONI, UFFICIO DI PRESIDENZA…
            continue
        if "presidenza" in cls:
            s["presidency"] = testo
            pid = re.search(r"idAnagrafe\.(\d+)", p.get("title") or "")
            s["presided_by"] = f"it:person:camera:{pid.group(1)}" if pid else None
            m = re.search(r"[–-]\s*(Interv\w+ .+)$", testo)
            s["government_present"] = m.group(1) if m else None
            continue
        m = re.search(r"riunit\w* dalle (\d{1,2}(?:[.,]\d{2})?) alle (\d{1,2}(?:[.,]\d{2})?)", testo)
        if m and not s.get("start_time"):                          # «L'ufficio di presidenza si è riunito dalle 14.35 alle 14.55.»
            s["start_time"], s["end_time"] = _ore(m.group(1)), _ore(m.group(2))
        if "avviso" in cls and _orario(testo):
            s["start_time" if re.search(r"comincia|inizia", testo, re.I) else "end_time"] = _orario(testo)
            continue
        if "titolo" in cls:
            ordini["punto"] += 1
            ordini["par"] = 0
            fase = next((c for c in reversed(p["corsivi"]) if c.strip().startswith("(")), None)
            u = f"{s_uri}:{(p['id'] or '').rsplit('.', 1)[-1] or ordini['punto']}"
            if u in uri_punti:  # la fonte a volte ripete l'id del titolo della sede precedente (bol. 29/6/2023, VII)
                u = f"{u}-{ordini['punto']}"
            uri_punti.add(u)
            punto = {"label": "AgendaItem", "uri": u,
                     "order": ordini["punto"], "title": _spazi(p["grassetti"][0]) if p["grassetti"] else testo,
                     "stage": _fase(fase), "acts": atti(testo)}
            nodi.append(punto)
            archi.append({"type": "HAS_ITEM", "from": s_uri, "to": punto["uri"], "order": ordini["punto"]})
            for ref in punto["acts"]:
                archi.append({"type": "ABOUT", "from": punto["uri"], "to_ref": ref})
            continue
        if not testo:
            continue
        # un paragrafo del sommario: intervento di una persona (con gruppo e ruolo) o testo degli uffici
        ordini["par"] += 1
        if punto is None:  # paragrafi prima del primo argomento (uffici di presidenza, comunicazioni)
            punto = {"label": "AgendaItem", "uri": f"{s_uri}:tit00000", "order": 0, "title": None, "stage": None, "acts": [], "service": True}
            nodi.append(punto)
            archi.append({"type": "HAS_ITEM", "from": s_uri, "to": punto["uri"], "order": 0})
        padre = punto["uri"]
        sp = f"{padre}:p{ordini['par']}"
        persona = p["persone"][0][0] if "intervento" in cls and p["persone"] else None
        ruolo = None
        if persona:
            dopo = testo[len(_spazi(p["persone"][0][1])):].lstrip(" ,")
            dopo = re.sub(r"^" + SIGLA.pattern + r"\s*,?\s*", "", dopo)
            m = re.match(r"^([a-zà-ù' ]{3,60}?),\s", dopo)
            ruolo = m.group(1).strip() if m and p["corsivi"] and m.group(1).strip() in _spazi(" ".join(p["corsivi"])) else None
        nodi.append({"label": "Speech", "uri": sp, "order": ordini["par"], "kind": "summary", "hash": _h(testo), "text_ref": f"speech:{sp}",
                     "speaker_label": _spazi(p["persone"][0][1]) if persona else None,
                     "declared_group": _sigla(p["gruppo"]), "as_office": ruolo,
                     "anchor": p["id"]})
        archi.append({"type": "HAS_SPEECH", "from": padre, "to": sp, "order": ordini["par"]})
        # deputati citati nel paragrafo (il primo link è chi parla): un arco per persona, il nome come lo scrive il testo
        archi += [{"type": "MENTIONS", "from": sp, "to": f"it:person:camera:{pid}", "order": i, "surface": _spazi(nome) or None, "method": "fonte"}
                  for i, (pid, nome) in enumerate(p["persone"][1:] if persona else p["persone"], 1) if pid]
        if persona:
            archi.append({"type": "BY", "from": sp, "to": f"it:person:camera:{persona}", "as_group": nodi[-1]["declared_group"], "as_office": ruolo})
        testi.append({"ref": f"speech:{sp}", "text": testo, "hash": _h(testo)})

    if allegati:
        a = leggi(allegati)
        blocchi: dict[str, list[str]] = {}
        for p in a.paragrafi:
            if p["sede"]:
                blocchi.setdefault(p["sede"], []).append(_spazi(p["testo"]))
        for i, (sid, righe) in enumerate(blocchi.items(), 1):
            testo = "\n".join(r for r in righe if r)
            if not testo:
                continue
            d_uri = f"{base}:allegato{i}"
            nodi.append({"label": "Document", "uri": d_uri, "kind": "annex", "date": data, "body_code": codice,
                         "title": " – ".join([r for r in righe if r][:2]) or None, "anchor": sid, "hash": _h(testo), "text_ref": f"document:{d_uri}",
                         "acts": atti(testo[:600]), "source": "camera_bollettino"})
            testi.append({"ref": f"document:{d_uri}", "text": testo, "hash": _h(testo)})
    return {"nodi": nodi, "archi": archi, "testi": testi,
            "ambito": {"kind": "commissione", "chamber": "camera", "legislature": leg, "date": data, "body_code": codice,
                       "source": "camera_bollettino", "source_key": fonte.get("chiave")}}
