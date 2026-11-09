"""Registro dei passi del giro notturno. Aggiungere una fonte: un connettore in `fonti/`, una trasformazione
in `trasforma/`, due righe qui e una sezione in `pipeline.toml`."""

from __future__ import annotations

import functools
import json
import re
import time

from . import documenti, fatti, termini, vettori
from .carica import postgres
from .controlli import uscite as controlli_uscite
from .fonti import eurovoc
from .fonti import camera_aic, camera_atti, camera_bollettino, camera_documenti, camera_dossier, camera_emendamenti, camera_governo, camera_ocd, camera_odg, camera_resoconti, camera_stenografici_commissioni, camera_testi, camera_voti, camera_webtv, senato_akn, senato_ddl, senato_esiti, senato_foto, senato_misto, senato_osr, senato_resoconti, senato_voti
from .lago import Lago
from .orchestra import Passo
from .trasforma import camera_anagrafica, camera_resoconto
from .trasforma import eurovoc as eurovoc_t
from .trasforma import camera_aic as camera_aic_t
from .trasforma import camera_atti as camera_atti_t
from .trasforma import camera_bollettino as camera_bollettino_t
from .trasforma import camera_governo as camera_governo_t
from .trasforma import camera_documenti as camera_documenti_t
from .trasforma import camera_dossier as camera_dossier_t
from .trasforma import camera_emendamenti as camera_emendamenti_t
from .trasforma import camera_odg as camera_odg_t
from .trasforma import camera_stenografico_commissione
from .trasforma import camera_testi as camera_testi_t
from .trasforma import corrispondenze, senato_anagrafica
from .trasforma import senato_ddl as senato_ddl_t
from .trasforma import senato_emendamenti, senato_resoconto, senato_sommario, senato_testi
from .trasforma import senato_voti as senato_voti_t
from .trasforma import camera_webtv as camera_webtv_t
from .trasforma import camera_voti as camera_voti_t


class DaRifare:
    """Grezzi che non si sono trasformati: il segno della fonte va avanti per gli altri, questi si riprovano al giro dopo
    (con la loro versione più recente) finché non riescono."""

    def __init__(self, cartella, segno: str):
        self.file = cartella / "uscite" / f".{segno}.da_rifare.json"
        self.chiavi = set(json.loads(self.file.read_text())) if self.file.exists() else set()

    def salva(self, chiavi: set[str]) -> None:
        if not chiavi:
            self.file.unlink(missing_ok=True)
            return
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(chiavi), ensure_ascii=False))
        tmp.replace(self.file)


def _grezzi(lago, fonte: str, da: float, rifare: DaRifare) -> dict[str, dict]:
    """Chiave -> versione più recente, per le chiavi arrivate dopo `da` e per quelle da rifare."""
    grezzi = {g["chiave"]: g for g in lago.ultimi_dal(fonte, da)}
    for k in rifare.chiavi - grezzi.keys():
        u = lago.ultimo(fonte, k)
        if u:
            grezzi[k] = {"chiave": k, **u}
    return grezzi


def _esito(fatti: int, errori: list[str], cosa: str) -> dict:
    """Riepilogo di una trasformazione: con qualche errore il passo riesce con un avviso; se non riesce nessun grezzo, fallisce."""
    if errori and not fatti:
        raise RuntimeError(f"nessun {cosa} trasformato, {len(errori)} errori (si riprovano al giro dopo): " + "; ".join(errori[:5]))
    r = {"trasformati": fatti, "errori": errori[:20]}
    if errori:
        r["avviso"] = f"{len(errori)} {cosa} non trasformati ({fatti} sì), si riprovano al giro dopo: " + "; ".join(errori[:3])
    return r


class Trasforma:
    """Trasforma i grezzi di una fonte salvati dopo l'ultimo giro (o tutti, al primo giro), una volta per chiave con la
    versione più recente. Un grezzo che non si trasforma non ferma gli altri: resta da rifare (`DaRifare`).
    È una classe e non una funzione annidata perché il passo gira in un processo a parte e va passato per copia."""

    def __init__(self, fonte: str, funzione, chiavi: str = "", segno: str = ""):
        self.fonte, self.funzione, self.chiavi = fonte, funzione, chiavi  # chiavi: espressione regolare sulle chiavi dei grezzi da trasformare
        self.segno = segno or fonte                                        # due passi sulla stessa fonte hanno segni diversi

    def __call__(self, ctx) -> dict:
        fonte, funzione = self.fonte, self.funzione
        lago, uscita = Lago(ctx.cartella), ctx.cartella / "uscite" / "v3" / fonte
        uscita.mkdir(parents=True, exist_ok=True)
        segno = ctx.cartella / "uscite" / f".{self.segno}.ultimo"
        da = float(segno.read_text()) if segno.exists() else 0.0
        rifare = DaRifare(ctx.cartella, self.segno)
        inizio, fatti, errori, falliti = time.time(), 0, [], set()
        for k, g in sorted(_grezzi(lago, fonte, da, rifare).items()):
            if not re.search(self.chiavi, k):
                continue
            try:
                _scrivi_jsonl(uscita / f"{k}.jsonl", funzione(lago.leggi(g["file"]), g))
                fatti += 1
            except Exception as e:  # un grezzo che non si legge non ferma gli altri: si riprova al giro dopo
                errori.append(f"{k}: {e}")
                falliti.add(k)
        rifare.salva(falliti)
        segno.write_text(str(inizio))
        return _esito(fatti, errori, "grezzi")


class TrasformaEmendamentiSenato(Trasforma):
    """Gli emendamenti del Senato con l'esito, che arriva da un'altra fonte: quando cambia il file degli esiti si
    ritrasformano tutti, non solo i grezzi nuovi."""

    def __init__(self):
        super().__init__("senato_akn", senato_emendamenti.trasforma, chiavi=r"-senato-eme-", segno="senato_akn_emendamenti")

    def __call__(self, ctx) -> dict:
        leg = int(ctx.config["fonti"][senato_esiti.NOME]["legislatura"])
        lago = Lago(ctx.cartella)
        esiti, impronta_esiti = senato_esiti.esiti(lago, leg)
        impronta = ctx.cartella / "uscite" / f".{self.segno}.esiti"
        if impronta_esiti != (impronta.read_text() if impronta.exists() else ""):
            (ctx.cartella / "uscite" / f".{self.segno}.ultimo").unlink(missing_ok=True)
        self.funzione = functools.partial(senato_emendamenti.trasforma, esiti=esiti)
        r = super().__call__(ctx)
        impronta.write_text(impronta_esiti)
        return {**r, "esiti": len(esiti)}


class TrasformaResocontiSenato(Trasforma):
    """I resoconti d'Aula del Senato, con l'indirizzo del resoconto ufficiale: per quelli importati senza l'id del documento
    lo si prende dal file del bulk con lo stesso numero di seduta (clone di senato_akn)."""

    def __init__(self):
        super().__init__("senato_resoconti", senato_resoconto.trasforma, chiavi=r"-senato-sed\d+$")

    def __call__(self, ctx) -> dict:
        cfg = ctx.config["fonti"][senato_akn.NOME]
        radice = (ctx.cartella / cfg.get("cartella_clone", "cache/senato_akn")).resolve() / f"Leg{int(cfg['legislatura'])}"
        documenti = {n: int(f.name.split("-")[0]) for n, f in senato_akn.sedute_resaula(radice).items()} if radice.is_dir() else {}
        self.funzione = functools.partial(senato_resoconto.trasforma, documenti=documenti)
        return {**super().__call__(ctx), "con_indirizzo_dal_bulk": len(documenti)}


def _scrivi_jsonl(file, r: dict) -> None:
    """Uscita di una trasformazione: una riga JSON per record, scritta in modo atomico."""
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        if r.get("ambito"):
            f.write(json.dumps({"tipo": "ambito", **r["ambito"]}, ensure_ascii=False) + "\n")
        for gruppo, tipo in (("nodi", "nodo"), ("archi", "arco"), ("testi", "testo")):
            for x in r[gruppo]:
                f.write(json.dumps({"tipo": tipo, **x}, ensure_ascii=False) + "\n")
    tmp.replace(file)


class TrasformaInsieme:
    """Per le fonti a query (anagrafica, atti): tutte le query si trasformano insieme, perché un record ne usa più
    d'una, e solo se almeno una è cambiata dal giro prima. `pagine` aggiunge grezzi di altre fonti che non sono JSON
    (nome -> (fonte, funzione chiave)), passati come testo e solo se ci sono nel lago."""

    def __init__(self, fonte: str, query: dict, funzione, uscita: str, kind: str, pagine: dict | None = None):
        self.fonte, self.query, self.funzione, self.uscita, self.kind = fonte, query, funzione, uscita, kind
        self.pagine = pagine or {}

    def __call__(self, ctx) -> dict:
        leg = int(ctx.config["fonti"][self.fonte]["legislatura"])
        lago = Lago(ctx.cartella)
        ultimi = {n: lago.ultimo(self.fonte, camera_ocd.chiave(n, leg)) for n in self.query}
        mancano = [n for n, u in ultimi.items() if not u]
        if mancano:
            raise RuntimeError(f"mancano nel lago: {mancano}")
        # getattr: un giro già partito passa oggetti creati prima che `pagine` esistesse
        pagine = {n: lago.ultimo(f, chiave(leg)) for n, (f, chiave) in getattr(self, "pagine", {}).items()}
        pagine = {n: u for n, u in pagine.items() if u}
        impronta = "-".join(u["impronta"][:8] for u in [*ultimi.values(), *pagine.values()])
        uscita = ctx.cartella / "uscite" / "v3" / self.fonte / f"leg{leg}-{self.uscita}.jsonl"
        segno = ctx.cartella / "uscite" / f".{self.fonte}.impronta"
        if uscita.exists() and segno.exists() and segno.read_text() == impronta:
            return {"trasformati": 0, "motivo": "dati invariati"}
        grezzi = {n: json.loads(lago.leggi(u["file"])) for n, u in ultimi.items()}
        grezzi.update({n: lago.leggi(u["file"]).decode("utf-8") for n, u in pagine.items()})
        r = self.funzione(grezzi, leg, {"chiave": f"leg{leg}-{self.uscita}", "impronta": impronta,
                                        **{f"{n}_url": u.get("url") for n, u in pagine.items()}})
        r["ambito"]["kind"] = self.kind
        _scrivi_jsonl(uscita, r)
        segno.write_text(impronta)
        return {"trasformati": 1, "nodi": len(r["nodi"]), "archi": len(r["archi"])}


class TrasformaBollettino:
    """Comunicato e allegati di una commissione in un giorno si trasformano insieme: si rifanno quando cambia l'uno o l'altro."""

    def __call__(self, ctx) -> dict:
        fonte = camera_bollettino.NOME
        lago, uscita = Lago(ctx.cartella), ctx.cartella / "uscite" / "v3" / fonte
        segno = ctx.cartella / "uscite" / f".{fonte}.ultimo"
        da = float(segno.read_text()) if segno.exists() else 0.0
        rifare = DaRifare(ctx.cartella, fonte)
        inizio, fatti, errori, falliti = time.time(), 0, [], set()
        basi = sorted({re.sub(r"-allegati$", "", k) for k in _grezzi(lago, fonte, da, rifare) if re.search(r"-c\w+(-allegati)?$", k)})
        for base in basi:
            try:
                c, a = lago.ultimo(fonte, base), lago.ultimo(fonte, base + "-allegati")
                if not c:
                    continue
                r = camera_bollettino_t.trasforma(lago.leggi(c["file"]), lago.leggi(a["file"]) if a else None,
                                                  {"chiave": base, "impronta": c["impronta"]})
                _scrivi_jsonl(uscita / f"{base}.jsonl", r)
                fatti += 1
            except Exception as e:
                errori.append(f"{base}: {e}")
                falliti.add(base)
        rifare.salva(falliti)
        segno.write_text(str(inizio))
        return _esito(fatti, errori, "comunicati")


class TrasformaDossier:
    """Scheda e testo di un dossier insieme, con i metadati presi dagli elenchi (data, servizio, nota)."""

    def __call__(self, ctx) -> dict:
        fonte = camera_dossier.NOME
        lago, uscita = Lago(ctx.cartella), ctx.cartella / "uscite" / "v3" / fonte
        segno = ctx.cartella / "uscite" / f".{fonte}.ultimo"
        da = float(segno.read_text()) if segno.exists() else 0.0
        rifare = DaRifare(ctx.cartella, fonte)
        inizio, fatti, errori, falliti = time.time(), 0, [], set()
        schede = [g for k, g in sorted(_grezzi(lago, fonte, da, rifare).items()) if k.endswith("-scheda")]
        meta: dict = {}
        if schede:
            for k in sorted(lago.chiavi(fonte)):
                if "-dossier-elenco-" in k:
                    meta.update(camera_dossier_t.metadati_elenco(lago.leggi(lago.ultimo(fonte, k)["file"])))
        for g in schede:
            try:
                t = lago.ultimo(fonte, g["chiave"].replace("-scheda", "-testo"))
                r = camera_dossier_t.trasforma(lago.leggi(g["file"]), lago.leggi(t["file"]) if t else None, meta, g)
                _scrivi_jsonl(uscita / f"{g['chiave']}.jsonl", r)
                fatti += 1
            except Exception as e:
                errori.append(f"{g['chiave']}: {e}")
                falliti.add(g["chiave"])
        rifare.salva(falliti)
        segno.write_text(str(inizio))
        return _esito(fatti, errori, "dossier")


def trasforma_corrispondenze(ctx) -> dict:
    """Corrispondenza fra gli id dei senatori nelle due fonti: dai senatori della Camera e dalle persone del Senato."""
    leg = int(ctx.config["fonti"]["senato_osr"]["legislatura"])
    lago = Lago(ctx.cartella)
    cam, osr = lago.ultimo("camera_ocd", camera_ocd.chiave("senatori", leg)), lago.ultimo("senato_osr", camera_ocd.chiave("persone", leg))
    if not cam or not osr:
        raise RuntimeError("mancano i senatori della Camera o le persone del Senato nel lago")
    impronta = cam["impronta"][:8] + "-" + osr["impronta"][:8]
    uscita = ctx.cartella / "uscite" / "v3" / "corrispondenze" / f"leg{leg}-corrispondenze.jsonl"
    segno = ctx.cartella / "uscite" / ".corrispondenze.impronta"
    if uscita.exists() and segno.exists() and segno.read_text() == impronta:
        return {"trasformati": 0, "motivo": "dati invariati"}
    r = corrispondenze.trasforma({"senatori_camera": json.loads(lago.leggi(cam["file"])), "senatori_osr": json.loads(lago.leggi(osr["file"]))},
                                 leg, {"chiave": f"leg{leg}-corrispondenze"})
    _scrivi_jsonl(uscita, r)
    segno.write_text(impronta)
    return {"trasformati": 1, "legati": len(r["archi"]), "senatori": len(r["nodi"])}


PASSI = [
    Passo("scarica_camera_resoconti", camera_resoconti.scarica, timeout_minuti=90, tentativi=2),
    Passo("trasforma_camera_resoconti", Trasforma("camera_resoconti", camera_resoconto.trasforma), dopo=["scarica_camera_resoconti"], timeout_minuti=60),
    Passo("scarica_camera_ocd", camera_ocd.scarica, timeout_minuti=30, tentativi=2),
    Passo("trasforma_camera_ocd", TrasformaInsieme("camera_ocd", camera_ocd.QUERY, camera_anagrafica.trasforma, "anagrafica", "anagrafica"),
          dopo=["scarica_camera_ocd"], timeout_minuti=15),
    Passo("scarica_camera_governo", camera_governo.scarica, timeout_minuti=15, tentativi=2),
    Passo("trasforma_camera_governo", TrasformaInsieme("camera_governo", camera_governo.QUERY, camera_governo_t.trasforma, "governo", "governo"),
          dopo=["scarica_camera_governo"], timeout_minuti=10),
    Passo("scarica_camera_atti", camera_atti.scarica, timeout_minuti=30, tentativi=2),
    Passo("trasforma_camera_atti", TrasformaInsieme("camera_atti", camera_atti.QUERY, camera_atti_t.trasforma, "atti", "atti"),
          dopo=["scarica_camera_atti"], timeout_minuti=15),
    Passo("scarica_camera_bollettino", camera_bollettino.scarica, timeout_minuti=90, tentativi=1),
    Passo("trasforma_camera_bollettino", TrasformaBollettino(), dopo=["scarica_camera_bollettino"], timeout_minuti=30),
    Passo("scarica_camera_stenografici_commissioni", camera_stenografici_commissioni.scarica, timeout_minuti=60, tentativi=1),
    Passo("trasforma_camera_stenografici_commissioni", Trasforma("camera_stenografici_commissioni", camera_stenografico_commissione.trasforma,
                                                                 chiavi=r"-stc-(?!elenco)"), dopo=["scarica_camera_stenografici_commissioni"], timeout_minuti=30),
    Passo("scarica_camera_aic", camera_aic.scarica, timeout_minuti=60, tentativi=2),
    Passo("trasforma_camera_aic", Trasforma("camera_aic", camera_aic_t.trasforma, chiavi=r"-aic-\d{6}$"), dopo=["scarica_camera_aic"], timeout_minuti=20),
    Passo("scarica_camera_webtv", camera_webtv.scarica, timeout_minuti=60, tentativi=1),
    Passo("trasforma_camera_webtv", Trasforma("camera_webtv", camera_webtv_t.trasforma, chiavi=r"-webtv-evento-"), dopo=["scarica_camera_webtv"], timeout_minuti=15),
    Passo("scarica_camera_odg", camera_odg.scarica, timeout_minuti=30, tentativi=2),
    Passo("trasforma_camera_odg", Trasforma("camera_odg", camera_odg_t.trasforma, chiavi=r"-odg-\d{8}$"), dopo=["scarica_camera_odg"], timeout_minuti=10),
    Passo("scarica_camera_documenti", camera_documenti.scarica, timeout_minuti=60, tentativi=1),
    Passo("trasforma_camera_documenti_elenchi", Trasforma("camera_documenti", camera_documenti_t.trasforma_elenco, chiavi=r"-doc-elenco-",
                                                          segno="camera_documenti_elenchi"), dopo=["scarica_camera_documenti"], timeout_minuti=10),
    Passo("trasforma_camera_documenti_testi", Trasforma("camera_documenti", camera_documenti_t.trasforma_file, chiavi=r"-doc-com\d+-",
                                                        segno="camera_documenti_testi"), dopo=["scarica_camera_documenti"], timeout_minuti=60),
    Passo("scarica_camera_dossier", camera_dossier.scarica, timeout_minuti=60, tentativi=1),
    Passo("trasforma_camera_dossier", TrasformaDossier(), dopo=["scarica_camera_dossier"], timeout_minuti=30),
    Passo("scarica_camera_emendamenti", camera_emendamenti.scarica, dopo=["scarica_camera_atti"], timeout_minuti=90, tentativi=1),
    Passo("trasforma_camera_emendamenti", Trasforma("camera_emendamenti", camera_emendamenti_t.trasforma, chiavi=r"-eme-ac"),
          dopo=["scarica_camera_emendamenti"], timeout_minuti=30),
    Passo("scarica_camera_testi", camera_testi.scarica, dopo=["scarica_camera_atti"], timeout_minuti=60, tentativi=1),
    Passo("trasforma_camera_testi", Trasforma("camera_testi", camera_testi_t.trasforma, chiavi=r"-testo-"), dopo=["scarica_camera_testi"], timeout_minuti=30),
    Passo("scarica_senato_osr", senato_osr.scarica, timeout_minuti=20, tentativi=1),
    Passo("scarica_senato_misto", senato_misto.scarica, timeout_minuti=10, tentativi=1),
    Passo("scarica_senato_foto", senato_foto.scarica, dopo=["scarica_senato_osr"], timeout_minuti=10, tentativi=1),
    Passo("trasforma_senato_osr", TrasformaInsieme("senato_osr", senato_osr.QUERY, senato_anagrafica.trasforma, "anagrafica", "anagrafica",
                                                   pagine={"misto": (senato_misto.NOME, senato_misto.chiave)}),
          dopo=["scarica_senato_osr", "scarica_senato_misto"], timeout_minuti=10),
    Passo("trasforma_corrispondenze", trasforma_corrispondenze, dopo=["scarica_camera_ocd", "scarica_senato_osr"], timeout_minuti=10),
    Passo("scarica_senato_ddl", senato_ddl.scarica, timeout_minuti=20, tentativi=1),
    Passo("trasforma_senato_ddl", TrasformaInsieme("senato_ddl", {"ddl": "", "firmatari": "", "presentatori": ""}, senato_ddl_t.trasforma, "atti", "atti"),
          dopo=["scarica_senato_ddl"], timeout_minuti=10),
    Passo("scarica_senato_aic", camera_aic.scarica_senato, timeout_minuti=60, tentativi=2),
    Passo("trasforma_senato_aic", Trasforma("senato_aic", camera_aic_t.trasforma_senato, chiavi=r"-aic-\d{6}$"), dopo=["scarica_senato_aic"], timeout_minuti=20),
    Passo("scarica_senato_resoconti", senato_resoconti.scarica, timeout_minuti=10, tentativi=1),
    Passo("scarica_senato_akn", senato_akn.scarica, timeout_minuti=120, tentativi=2),
    Passo("trasforma_senato_resoconti", TrasformaResocontiSenato(),
          dopo=["scarica_senato_resoconti", "scarica_senato_akn"], timeout_minuti=60),
    Passo("trasforma_senato_sommari", Trasforma("senato_akn", senato_sommario.trasforma, chiavi=r"-senato-som-", segno="senato_akn_sommari"),
          dopo=["scarica_senato_akn"], timeout_minuti=60),
    Passo("trasforma_senato_testi", Trasforma("senato_akn", senato_testi.trasforma, chiavi=r"-senato-testo-", segno="senato_akn_testi"),
          dopo=["scarica_senato_akn"], timeout_minuti=60),
    Passo("scarica_senato_esiti", senato_esiti.scarica, dopo=["scarica_senato_ddl"], timeout_minuti=20, tentativi=1),
    # senza gli esiti di stanotte valgono quelli già nel lago
    Passo("trasforma_senato_emendamenti", TrasformaEmendamentiSenato(), dopo=["scarica_senato_akn"], dopo_comunque=["scarica_senato_esiti"], timeout_minuti=60),
    Passo("scarica_senato_voti", senato_voti.scarica, timeout_minuti=60, tentativi=1),
    Passo("trasforma_senato_voti", Trasforma("senato_voti", senato_voti_t.trasforma, chiavi=r"-senato-voti-sed"), dopo=["scarica_senato_voti"], timeout_minuti=30),
    Passo("scarica_camera_voti", camera_voti.scarica, timeout_minuti=120, tentativi=2),
    Passo("trasforma_camera_voti", Trasforma("camera_voti", camera_voti_t.trasforma, chiavi="-voti-sed"), dopo=["scarica_camera_voti"], timeout_minuti=60),
    Passo("scarica_eurovoc", eurovoc.scarica, timeout_minuti=10, tentativi=2),
    Passo("trasforma_eurovoc", Trasforma("eurovoc", eurovoc_t.trasforma), dopo=["scarica_eurovoc"], timeout_minuti=5),
    # i controlli e il caricamento vengono dopo tutte le trasformazioni, ma una trasformazione fallita non li ferma:
    # si caricano le uscite delle altre fonti
    Passo("controlla_uscite", controlli_uscite.controlla, dopo_comunque=["trasforma_eurovoc", "trasforma_camera_resoconti", "trasforma_camera_ocd", "trasforma_camera_governo", "trasforma_camera_atti", "trasforma_camera_voti",
                                                          "trasforma_camera_bollettino", "trasforma_camera_stenografici_commissioni",
                                                          "trasforma_camera_aic", "trasforma_camera_webtv",
                                                          "trasforma_camera_odg", "trasforma_camera_documenti_elenchi",
                                                          "trasforma_camera_documenti_testi", "trasforma_camera_dossier",
                                                          "trasforma_camera_emendamenti", "trasforma_camera_testi",
                                                          "trasforma_senato_osr", "trasforma_senato_voti",
                                                          "trasforma_senato_ddl", "trasforma_senato_aic",
                                                          "trasforma_corrispondenze", "trasforma_senato_resoconti",
                                                          "trasforma_senato_emendamenti", "trasforma_senato_sommari",
                                                          "trasforma_senato_testi"], timeout_minuti=30, critico=True),
    # il caricamento ha il suo tempo ([carica] tempo_minuti, 150): si ferma da solo fra un file e l'altro e riprende al giro dopo
    Passo("carica_postgres", postgres.carica, dopo=["controlla_uscite"], timeout_minuti=200, critico=True, usa_db=True),
    Passo("documenti_parlamentari", documenti.passo, dopo=["carica_postgres"], timeout_minuti=15, tentativi=1, usa_db=True),
    # dai sommari caricati: regole e seconda lettura con la Batch API (si aspetta al più [termini] attesa_minuti)
    Passo("termini_emendamenti", termini.passo, dopo=["carica_postgres"], timeout_minuti=40, tentativi=1, usa_db=True),
    # fatti delle commissioni dai sommari (audizioni, pareri, iter…): una lettura per argomento con la Batch API
    Passo("fatti_sommari", fatti.passo, dopo=["carica_postgres"], timeout_minuti=40, tentativi=1, usa_db=True),
    Passo("raccogli_vettori", vettori.passo_raccogli, timeout_minuti=60, tentativi=2, usa_db=True),
    Passo("taglia_brani", vettori.passo_taglia, dopo=["carica_postgres"], timeout_minuti=60, usa_db=True),
    Passo("invia_vettori", vettori.passo_invia, dopo=["taglia_brani", "raccogli_vettori"], timeout_minuti=60, tentativi=2, usa_db=True),
    Passo("controlla_indice", vettori.passo_controlla_indice, dopo_comunque=["invia_vettori"], timeout_minuti=5, usa_db=True),
]

for _p in PASSI:
    if _p.nome.startswith("scarica_camera_") or _p.nome == "scarica_senato_aic":
        _p.sito = "camera"          # tutti da *.camera.it: dopo un 403 o un 503 la Camera blocca l'IP, gli altri si saltano
    if _p.nome.startswith(("trasforma_", "controlla_", "carica_")):
        _p.limite_giro = False      # lavoro locale e caricamento: partono anche se i download hanno finito il tempo del giro
    if _p.nome == "scarica_senato_foto":
        _p.usa_db = True
