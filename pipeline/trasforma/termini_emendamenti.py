"""Dai sommari delle commissioni (Bollettino della Camera, resoconti sommari del Senato) ai termini per gli emendamenti:
la data e l'ora di scadenza, il tipo (emendamenti, subemendamenti, ordini del giorno, riesame delle inammissibilità) e
l'evento (fissato, prorogato, scaduto). «Il termine per la presentazione delle proposte emendative è fissato alle ore 12
di lunedì 9 novembre» (X Commissione della Camera, 4/11/2026) → 2026-11-09 12:00, fissato.

Regole fisse, trasformazione pura. Quando la frase non rientra in uno schema sicuro (una richiesta, un'ipotesi, due date
senza una proroga, un giorno della settimana che non torna con la data) il termine non si crea e resta il motivo.
Precisione misurata a mano su frasi mai viste (9/11/2026): data giusta in 92-95 casi su 100. Per questo ogni termine
passa anche da una seconda lettura con un modello (pipeline/termini.py) prima di entrare nel database.
"""

from __future__ import annotations

import datetime as dt
import re

MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                                     "settembre", "ottobre", "novembre", "dicembre"], 1)}
GIORNI = {"lunedì": 0, "lunedi": 0, "martedì": 1, "martedi": 1, "mercoledì": 2, "mercoledi": 2, "giovedì": 3, "giovedi": 3,
          "venerdì": 4, "venerdi": 4, "sabato": 5, "domenica": 6}
NOME_G = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
NOMI_G = r"(lunedì|lunedi|martedì|martedi|mercoledì|mercoledi|giovedì|giovedi|venerdì|venerdi|sabato|domenica)"
SETT = rf"(?:{NOMI_G},?\s+)?"
MESE = r"(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
ORA = r"(?:ore\s+(\d{1,2})(?:[,.:](\d{2}))?)"

TERMINE = re.compile(r"(?<!al )(?<!Al )termin[ei]\b(?! (?:di|della|per la) (?:proroga|delega|l'esercizio|prescrizione|decadenza))(?! (?:del|della|dei|delle|degli|dello) (?:votazion|sedut|esame|lavori|discussion|intervent|audizion))[^.;]{0,120}?(?:sub-?)?(?:emendament|emendativ)\w*", re.I)
RICHIESTA = re.compile(r"\b(?:chiede|chiedono|chiedere|chiesto|richiesto|richiesta di|propone|propongono|proposto di|ritiene opportuno|auspica|invita|"
                       r"sollecita\w*|apprezzando|potrebbe|può essere fissato)\b", re.I)
DECISIONE = re.compile(r"convien\w*|convenut\w*|concord\w*|così (?:rimane )?stabilito|(?:è|sono) (?:stato |stati )?(?:posticipat|prorogat|differit|fissat)\w*", re.I)
VECCHIA = re.compile(r"(?:già|inizialmente|precedentemente|in precedenza|originariamente) (?:fissat|stabilit|previst)\w*\s+(?:per\s+|a\s+|al\s+|alle\s+|il\s+)?(?:giorno\s+)?$", re.I)
NEGAZIONE = re.compile(r"\bnon\b[^.;]{0,40}?(?:fissar|posticip|prorog|ritenendo|differi)", re.I)
SEGNALATI = re.compile(r"segnalat", re.I)
SUB = re.compile(r"sub-?emendament|sub-?emendativ", re.I)
ODG = re.compile(r"ordini del giorno", re.I)
RIESAME = re.compile(r"riesame", re.I)
PROROGA = re.compile(r"(?<!im)prorog|posticip|differi|sposta|riapert|riaprire|slitta|anticipa|(?:è|sia) stato rinviat", re.I)
IPOTESI = re.compile(r"prefigura|possibilità|qualora|eventualmente|ipotesi|ipotizza", re.I)
SCADUTO = re.compile(r"allo scadere|alla scadenza del(?:l[ao])? (?:relativ\w+ )?termin|(?:è|e'|sono|era|erano) (?:ormai |già |appena )?scadut|"
                     r"scadut[oi] (?:il|i) termin|decors", re.I)
PASSATO = re.compile(r"era (?:stato )?fissat|erano (?:stati )?fissat|precedente seduta|scors|precedentemente|già fissat|aveva fissat|inizialmente|al momento fissat", re.I)
FUTURO_SENZA_DATA = re.compile(r"sarà fissato|potrà essere fissato|verrà fissato|saranno fissat|si riserva di fissare|da fissare|"
                               r"fissare (?:il|un) termine|fissazione del termine|sarà stabilito|verrà stabilito|sarà definito", re.I)
FISSATO = re.compile(r"fissat|fissa\b|fissano|fissare|stabilit|scade\b|scadrà|scadono|scadranno|convenut|entro le ore|"
                     r"termin[ei] (?:di|del|dell[ae]|alle|per)\b|resta|rimane|è posto", re.I)
CONTO = re.compile(r"(?:sono (?:stat[ie] )?(?:presentat|pervenut|depositat)\w*|risultano (?:presentat|pervenut)\w*)\s+(?:complessivamente\s+)?(?:n\.\s*)?(\d[\d.]*)", re.I)

# una data scritta: «alle ore 12 di lunedì 9 novembre 2026», «giovedì 22, alle ore 14», «10 gennaio 2023, alle ore 15»
DATA = re.compile(rf"(?:{ORA}\s+(?:del(?:la)?\s+(?:giorno|giornata\s+di)?\s*|di\s+|dell[ae]?\s+)?)?(?:giorno\s+)?{SETT}(\d{{1,2}})(?:°|º)?(?:\s+{MESE})?(?:\s+(\d{{4}}))?(?:\s*,?\s*(?:alle\s+)?{ORA})?", re.I)
RELATIVA = re.compile(rf"(?:{ORA}\s+(?:di|della|del)\s+(?:giornata\s+)?)?(oggi|odiern[ao]|domani|dopodomani|ieri)(?:\s*,?\s*(?:alle\s+)?{ORA})?", re.I)
PROSSIMO = re.compile(rf"(?:{ORA}\s+(?:di|del)\s+)?{NOMI_G}\s+prossim[oa](?:\s*,?\s*(?:alle\s+)?{ORA})?", re.I)
AGGETTIVO = re.compile(r"(?:riunione|seduta|sedute)\s+$", re.I)                 # «riunione odierna» non è la scadenza
ABBREV = re.compile(r"\b(n|C|S|A|art|artt|Doc|Atto|ddl|pag|on|sen|prof|dott|lett|co|cfr|ecc)\.\s*$", re.I)


def frasi(t: str) -> list[str]:
    """Il testo in frasi, senza spezzare «C. 3120», «n. 506», «art. 81»."""
    out, buf = [], ""
    for pezzo in re.split(r"(?<=[.;])\s+", t):
        buf = f"{buf} {pezzo}".strip() if buf else pezzo
        if ABBREV.search(buf):
            continue
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return out


def _ora(h: str | None, m: str | None) -> str | None:
    if not h or int(h) > 24:
        return None
    return f"{int(h):02d}:{m or '00'}"


def date_nella_frase(f: str, base: dt.date) -> list[dict]:
    """Le date nella frase, con posizione, ora, giorno della settimana dichiarato."""
    trovate = []
    for m in RELATIVA.finditer(f):
        parola, ora = m.group(3).lower(), _ora(m.group(1), m.group(2)) or _ora(m.group(4), m.group(5))
        fine = m.end(3) if m.group(1) else m.end()             # «alle ore 12 di domani, alle ore 12 di mercoledì 12»: la seconda ora è dell'altra data
        if parola.startswith("odiern") and not ora and AGGETTIVO.search(f[:m.start()]):
            continue
        if not ora and re.match(r"\s*(?:\w+\s+)?(?:era|è|erano)?\s*(?:stat[oiae]\s+)?(?:fissat|stabilit|convenut|depositat|adottat)", f[m.end():], re.I):
            continue                                            # «ieri era stato fissato», «i testi oggi depositati»: non è la scadenza
        giorno = base + dt.timedelta(days={"domani": 1, "dopodomani": 2, "ieri": -1}.get(parola, 0))
        trovate.append({"pos": m.start(), "fine": fine, "data": giorno, "ora": ora, "settimana": None, "testo": f[m.start():fine]})
    for m in PROSSIMO.finditer(f):
        w = GIORNI[m.group(3).lower()]
        giorno = base + dt.timedelta(days=(w - base.weekday() - 1) % 7 + 1)
        trovate.append({"pos": m.start(), "fine": m.end(), "data": giorno, "ora": _ora(m.group(1), m.group(2)) or _ora(m.group(4), m.group(5)),
                        "settimana": None, "testo": m.group(0)})
    for m in DATA.finditer(f):
        h1, mi1, sett, g, mese, anno, h2, mi2 = m.groups()
        if not mese and not sett:
            continue                                            # un numero qualsiasi («22 emendamenti»)
        if any(t["pos"] <= m.start() < t["fine"] for t in trovate):
            continue
        if not mese and re.match(r"\s*(?:emendament|propost|ordin|subemend)", f[m.end():], re.I):
            continue
        g = int(g)
        if mese:
            mm = MESI[mese.lower()]
        elif sett:                                              # «mercoledì 6»: il mese vicino alla seduta in cui il 6 è mercoledì
            vicini = []
            for k in (-1, 0, 1):
                a, mmk = base.year + (base.month - 1 + k) // 12, (base.month - 1 + k) % 12 + 1
                try:
                    x = dt.date(a, mmk, g)
                except ValueError:
                    continue
                if x.weekday() == GIORNI[sett.lower()]:
                    vicini.append(x)
            mm = min(vicini, key=lambda x: abs((x - base).days)).month if vicini else (base.month if g >= base.day else base.month % 12 + 1)
        else:
            mm = base.month if g >= base.day else base.month % 12 + 1
        trovate.append({"pos": m.start(), "fine": m.end(), "g": g, "m": mm, "anno": int(anno) if anno else None,
                        "ora": _ora(h1, mi1) or _ora(h2, mi2), "settimana": GIORNI.get(sett.lower()) if sett else None,
                        "testo": m.group(0).strip()})
    return sorted(trovate, key=lambda d: d["pos"])


def risolvi(d: dict, base: dt.date, passato: bool) -> tuple[dt.date | None, str | None]:
    """L'anno mancante. Con il giorno della settimana: l'anno, fra quello della seduta e i due vicini, in cui il giorno
    torna; senza: per un termine futuro il primo giorno dalla seduta in poi, per un termine passato l'ultimo prima."""
    if "data" in d:
        return d["data"], None
    try:
        if d["anno"]:
            x = dt.date(d["anno"], d["m"], d["g"])
            if d["settimana"] is not None and x.weekday() != d["settimana"]:
                return None, f"giorno della settimana incoerente: «{d['testo']}» ({x.isoformat()} è {NOME_G[x.weekday()]})"
            return x, None
        cand = [dt.date(a, d["m"], d["g"]) for a in (base.year - 1, base.year, base.year + 1)]
    except ValueError:
        return None, "data impossibile"
    if d["settimana"] is not None:
        vicine = [x for x in cand if x.weekday() == d["settimana"] and abs((x - base).days) <= 200]
        if not vicine:
            v = min(cand, key=lambda x: abs((x - base).days))
            return None, f"giorno della settimana incoerente: «{d['testo']}» ({v.isoformat()} è {NOME_G[v.weekday()]})"
        return min(vicine, key=lambda x: abs((x - base).days)), None
    if not passato:
        x = min(x for x in cand if x >= base - dt.timedelta(days=1))
        if (x - base).days <= 150:                              # un termine fra più di cinque mesi, senza anno, è un termine passato
            return x, None
    return max(x for x in cand if x <= base + dt.timedelta(days=1)), None


def estrai(r: dict) -> list[dict]:
    """Le frasi di un paragrafo che parlano di un termine. `r`: speech, kind, chamber, date (della seduta), body_name,
    item_title, acts ([{ref, act}]), text. Ogni frase esce con `esito`: estratto (con scadenza, ora, evento, tipo),
    senza data, scartato o non riconosciuto (con il motivo)."""
    if r.get("kind") != "summary":                              # negli interventi i termini sono discorsi, non decisioni
        return []
    base = dt.date.fromisoformat(r["date"])
    out = []
    elenco = frasi(re.sub(r"\s+", " ", r["text"]))
    for n, f in enumerate(elenco):
        seguito = elenco[n + 1] if n + 1 < len(elenco) else ""   # «Il PRESIDENTE propone… » / «La Commissione conviene.»
        t = TERMINE.search(f)
        if not t:
            continue
        e = {"speech": r["speech"], "chamber": r["chamber"], "date": r["date"], "body_name": re.sub(r"\s+", " ", r["body_name"] or "").strip(),
             "item_title": r.get("item_title"), "acts": [a["ref"] for a in (r.get("acts") or [])], "frase": f, "seguito": seguito}
        finestra = f[t.start():t.end() + 60]                      # il tipo si legge subito dopo «termine»
        if RIESAME.search(finestra):
            e["tipo"] = "riesame delle inammissibilità"
        elif SEGNALATI.search(finestra):
            e["tipo"] = "segnalazione degli emendamenti"
        else:
            e["tipo"] = "subemendamenti" if SUB.search(t.group(0)) else "emendamenti"
            if ODG.search(finestra) or ODG.search(f[max(0, t.start() - 40):t.start()]):
                e["tipo"] += " e ordini del giorno"
        if NEGAZIONE.search(f):
            e["esito"], e["motivo"] = "scartato", "frase negativa («non fissare», «non posticipare»)"
            out.append(e)
            continue
        if IPOTESI.search(f) and not DECISIONE.search(f):
            e["esito"], e["motivo"] = "scartato", "ipotesi («prefigura la possibilità», «qualora»)"
            out.append(e)
            continue
        if RICHIESTA.search(f) and not DECISIONE.search(f) and not re.match(r"\s*(?:La Commissione|Le Commissioni|Non facendosi osservazioni|Conviene|Concord|Così rimane)[^.]{0,40}(?:convien|concord|stabilito|osservazioni)", seguito, re.I):
            e["esito"], e["motivo"] = "scartato", "richiesta o proposta, non decisione"
            out.append(e)
            continue
        conto = CONTO.search(f)
        limite = conto.start() if conto and conto.start() > t.start() else t.end() + 160
        date = [d for d in date_nella_frase(f, base) if t.start() - 90 <= d["pos"] < limite]   # solo le date legate al termine
        proroga = PROROGA.search(f)
        if SCADUTO.search(f) and not proroga and not re.search(r"rinviat", f, re.I):
            e["evento"], passato = "scaduto", True
            if conto:
                e["presentati"] = int(conto.group(1).replace(".", ""))
        elif proroga:
            e["evento"], passato = "prorogato", False
        elif FUTURO_SENZA_DATA.search(f) and (not date or all(d.get("data") and not d["ora"] for d in date)):
            # «sarà fissato nella riunione già convocata per domani»: la data è della riunione, non del termine
            e["evento"], e["esito"] = "annunciato", "senza data"
            out.append(e)
            continue
        elif FISSATO.search(f):
            e["evento"], passato = "fissato", bool(PASSATO.search(f))
        else:
            e["esito"], e["motivo"] = "non riconosciuto", "nessuna formula nota"
            out.append(e)
            continue
        sola_ora = re.search(rf"(?:alle|per le|delle|dalle)\s+{ORA[3:-1]}|alle\s+(\d{{1,2}})[.,:](\d{{2}})\b", f[t.start():], re.I)
        if not date and sola_ora and e["evento"] in ("fissato", "prorogato"):
            h, mi = (sola_ora.group(1), sola_ora.group(2)) if sola_ora.group(1) else (sola_ora.group(3), sola_ora.group(4))
            if _ora(h, mi):                                     # «scade alle ore 15,30»: il giorno è quello della seduta
                date = [{"pos": t.start() + sola_ora.start(), "fine": 0, "data": base, "ora": _ora(h, mi), "settimana": None,
                         "testo": sola_ora.group(0) + " (giorno della seduta)"}]
        if not date:
            e["esito"] = "senza data" if e["evento"] == "scaduto" else "non riconosciuto"
            if e["esito"] == "non riconosciuto":
                e["motivo"] = "formula nota ma nessuna data leggibile"
            out.append(e)
            continue
        if proroga:                                             # la data nuova è la prima dopo «prorogato», «posticipare»
            nuove = [d for d in date if d["pos"] > proroga.start() and not VECCHIA.search(f[max(0, d["pos"] - 40):d["pos"]])]
            dopo = [d for d in nuove if d["pos"] > t.start()] or nuove   # «già fissato per martedì 21»: è la data vecchia
            if not dopo:
                e["esito"], e["motivo"] = "scartato", "proroga senza data nuova"
                out.append(e)
                continue
            scelta = dopo[0]
        else:
            dopo = [d for d in date if d["pos"] >= t.start()]
            distinte = {(d.get("g"), d.get("m"), d.get("data")) for d in dopo}
            if len(distinte) > 1 and PASSATO.search(f):
                e["esito"], e["motivo"] = "scartato", "due date dopo «termine», una superata"
                e["date_viste"] = [d["testo"] for d in dopo]
                out.append(e)
                continue
            scelta = dopo[0] if dopo else date[-1]              # «alle ore 18 di venerdì 11 maggio è scaduto il termine»
        if re.search(r"\d\s+o\s+(?:al|all'|il|l')\s*\d", f):
            e["esito"], e["motivo"] = "scartato", "data alternativa («il 7 o l'8»)"
            out.append(e)
            continue
        if not scelta["ora"]:                                   # «oggi, martedì 25 luglio, alle ore 17.30»; «alle 13 di oggi»
            cerca = rf"{ORA}|alle\s+(\d{{1,2}})(?:[.,](\d{{2}}))?\b"   # prima dopo la data, poi subito prima
            vicino = re.search(cerca, f[scelta["pos"]:scelta["fine"] + 30], re.I) or re.search(cerca, f[max(0, scelta["pos"] - 25):scelta["pos"]], re.I)
            if vicino:
                scelta["ora"] = _ora(vicino.group(1), vicino.group(2)) if vicino.group(1) else _ora(vicino.group(3), vicino.group(4))
        if e["evento"] != "scaduto":                            # «scorso» vale per la data che segue, non per tutta la frase
            passato = bool(PASSATO.search(f[max(0, scelta["pos"] - 50):scelta["fine"] + 15]))
        giorno, problema = risolvi(scelta, base, passato)
        if problema:
            e["esito"], e["motivo"] = "scartato", problema
            out.append(e)
            continue
        if not e["acts"]:
            e["avviso"] = "argomento senza atto collegato"
        elif len(e["acts"]) > 1:
            e["avviso"] = f"{len(e['acts'])} atti abbinati"
        e.update(scadenza=giorno.isoformat(), ora=scelta["ora"], testo_data=scelta["testo"],
                 controllo_settimana=scelta.get("settimana") is not None, esito="estratto")
        out.append(e)
    return out

