"""Esiti degli emendamenti del Senato, in commissione e in Assemblea. I bulk data Akoma Ntoso danno testo e firmatari
ma non l'esito: lo dà la scheda di ogni lettura su senato.it (scheda-ddl?tab=testiEmendamenti&did={idFase}), una voce
per emendamento con il link al file (tipodoc=EMEND o EMENDC, con lo stesso id del file Akoma Ntoso:
01521763-em.akn.xml ↔ 1521763) e l'esito. senato.it sta dietro il WAF: le pagine si aprono con il browser senza
interfaccia (senato_browser).

Base: il CSV già estratto da quelle pagine l'8/10/2026 (`file_import`: id_fase, sede, id_testo, numero, esito). Ogni
giro riscarica al più `massimo_richieste` letture, nell'ordine: mai viste; in esame in commissione e non controllate da
`giorni_ricontrollo` giorni; con lo stato cambiato dall'ultima volta. Le letture senza esame non si chiedono.
Chiavi nel lago: `leg19-senato-esiti` (il CSV), `leg19-senato-esiti-{idFase}` (le pagine), `leg19-senato-esiti-stati`
(lo stato di ogni lettura al momento in cui la sua pagina è stata scaricata).
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import io
import json
import re

from ..ambiente import percorso
from ..lago import Lago
from . import senato_browser

NOME = "senato_esiti"
CAMPI = ["id_fase", "sede", "id_testo", "numero", "esito"]
PAGINA = "https://www.senato.it/leggi-e-documenti/disegni-di-legge/scheda-ddl?tab=testiEmendamenti&did={fase}"
VOCE = re.compile(r'tipodoc=(EMENDC?)&amp;id=(\d+)[^"]*">([^<]+)</a>\s*</dt>\s*<dd>(.*?)</dd>', re.S)
SENZA_ESAME = {"assegnato (no esame)", "da assegn. a commis.", "ritirato", "assorbito"}
IN_ESAME = "esame in comm."


def chiave(leg: int) -> str:
    return f"leg{leg}-senato-esiti"


def leggi(corpo: bytes) -> dict[str, str]:
    """Dal CSV: id_testo -> esito, solo le righe con un esito."""
    return {r["id_testo"].lstrip("0"): r["esito"].strip() for r in csv.DictReader(io.StringIO(corpo.decode("utf-8")))
            if r.get("id_testo") and (r.get("esito") or "").strip()}


def leggi_pagina(corpo: bytes) -> dict[str, str]:
    """Dalla scheda di una lettura: id_testo -> esito, solo le voci con un esito."""
    out = {}
    for _tipo, ident, _numero, dd in VOCE.findall(corpo.decode("utf-8", errors="replace")):
        esito = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", dd)).split())
        if esito:
            out[ident.lstrip("0")] = esito
    return out


def esiti(lago: Lago, leg: int) -> tuple[dict[str, str], str]:
    """Tutti gli esiti, la base del CSV corretta dalle pagine scaricate dopo, e un'impronta che cambia con loro."""
    out, impronte = {}, []
    u = lago.ultimo(NOME, chiave(leg))
    if u:
        out.update(leggi(lago.leggi(u["file"])))
        impronte.append(u["impronta"][:8])
    for k in sorted(lago.chiavi(NOME)):
        if re.fullmatch(rf"leg{leg}-senato-esiti-\d+", k):
            p = lago.ultimo(NOME, k)
            out.update(leggi_pagina(lago.leggi(p["file"])))
            impronte.append(p["impronta"][:8])
    return out, "-".join(impronte)


def _da_scaricare(letture: list[dict], stati: dict, base: set[str], oggi: dt.date, giorni: int) -> list[str]:
    nuove, vecchie, cambiate = [], [], []
    for r in sorted(letture, key=lambda r: r.get("data") or "", reverse=True):
        fase, stato = r["ddl"].rsplit("/", 1)[-1], (r.get("stato") or "").strip()
        if stato in SENZA_ESAME:
            continue
        visto = stati.get(fase)
        if visto is None:
            # nel CSV di base: si considera visto allora, con lo stato di oggi se l'esame è chiuso
            if fase in base and stato != IN_ESAME:
                continue
            if fase in base:
                vecchie.append(("", fase))               # dal CSV di base: controllate prima delle altre in esame
            else:
                nuove.append(fase)
        elif stato != visto["stato"]:
            cambiate.append(fase)
        elif stato == IN_ESAME and (oggi - dt.date.fromisoformat(visto["il"])).days >= giorni:
            vecchie.append((visto["il"], fase))
    return nuove + [fase for _, fase in sorted(vecchie)] + cambiate


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg = int(cfg["legislatura"])
    lago = Lago(ctx.cartella)
    importati = 0
    f = percorso(cfg["file_import"]) if cfg.get("file_import") else None
    if f and f.is_file():
        corpo = f.read_bytes()
        if csv.DictReader(io.StringIO(corpo.decode("utf-8"))).fieldnames != CAMPI:
            raise RuntimeError(f"{f}: colonne attese {CAMPI}")
        importati = int(lago.salva(NOME, chiave(leg), corpo, "https://www.senato.it/leggi-e-documenti/disegni-di-legge", "csv")["nuovo"])
    u = lago.ultimo("senato_ddl", f"leg{leg}-ddl")
    if not u or not cfg.get("scarica", True):
        return {"importati": importati, "pagine": 0}
    letture = json.loads(lago.leggi(u["file"]))
    s = lago.ultimo(NOME, f"leg{leg}-senato-esiti-stati")
    stati = json.loads(lago.leggi(s["file"])) if s else {}
    per_fase = {r["ddl"].rsplit("/", 1)[-1]: (r.get("stato") or "").strip() for r in letture}
    # pagine nel lago senza stato (un giro interrotto prima di salvarlo): valgono come viste il giorno in cui sono arrivate
    for k in lago.chiavi(NOME):
        fase = k.rsplit("-", 1)[-1]
        if re.fullmatch(rf"leg{leg}-senato-esiti-\d+", k) and fase not in stati:
            stati[fase] = {"stato": per_fase.get(fase, ""), "il": dt.date.fromtimestamp(lago.ultimo(NOME, k)["scaricato"]).isoformat()}
    b = lago.ultimo(NOME, chiave(leg))
    base = {r["id_fase"] for r in csv.DictReader(io.StringIO(lago.leggi(b["file"]).decode("utf-8")))} if b else set()
    oggi = dt.date.today()
    coda = _da_scaricare(letture, stati, base, oggi, int(cfg.get("giorni_ricontrollo", 7)))
    fatte, motivo, mancanti = 0, "finite", []
    try:
        with senato_browser.Sessione(pausa=float(cfg.get("pausa_secondi", 3)), massimo=int(cfg.get("massimo_richieste", 150)), ctx=ctx) as sessione:
            for fase in coda:
                url = PAGINA.format(fase=fase)
                try:
                    corpo = sessione.scarica(url)
                except senato_browser.NonTrovato:
                    # la scheda non c'è: vale come vista oggi, così non si richiede a ogni giro; si riprova se cambia lo stato
                    stati[fase] = {"stato": per_fase.get(fase, ""), "il": oggi.isoformat(), "non_trovata": True}
                    mancanti.append(fase)
                    continue
                lago.salva(NOME, f"leg{leg}-senato-esiti-{fase}", corpo, url, "html")
                stati[fase] = {"stato": per_fase.get(fase, ""), "il": oggi.isoformat()}
                fatte += 1
    except senato_browser.Bloccato as e:
        motivo = str(e)                                  # si riprende al giro dopo da dove si è fermato
    finally:
        lago.salva(NOME, f"leg{leg}-senato-esiti-stati", json.dumps(stati, ensure_ascii=False, sort_keys=True).encode(), "", "json")
    ctx.log(f"{NOME}: {fatte} pagine su {len(coda)} in coda, {len(mancanti)} non trovate ({motivo})")
    return {"importati": importati, "pagine": fatte, "non_trovate": mancanti[:20], "in_coda": len(coda) - fatte - len(mancanti)}
