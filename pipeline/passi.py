"""Registro dei passi del giro notturno. Aggiungere una fonte: un connettore in `fonti/`, una trasformazione
in `trasforma/`, due righe qui e una sezione in `pipeline.toml`."""

from __future__ import annotations

import json
import re
import time

from . import vettori
from .carica import postgres
from .controlli import uscite as controlli_uscite
from .fonti import eurovoc
from .fonti import camera_aic, camera_atti, camera_bollettino, camera_documenti, camera_dossier, camera_emendamenti, camera_governo, camera_ocd, camera_odg, camera_resoconti, camera_stenografici_commissioni, camera_testi, camera_voti, camera_webtv, senato_akn, senato_ddl, senato_osr, senato_resoconti, senato_voti
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


class Trasforma:
    """Trasforma i grezzi di una fonte salvati dopo l'ultimo giro riuscito (o tutti, al primo giro).
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
        inizio, fatti, errori = time.time(), 0, []
        for g in lago.nuovi_dal(fonte, da):
            if not re.search(self.chiavi, g["chiave"]):
                continue
            try:
                _scrivi_jsonl(uscita / f"{g['chiave']}.jsonl", funzione(lago.leggi(g["file"]), g))
                fatti += 1
            except Exception as e:  # un grezzo che non si legge non ferma gli altri, ma ferma il giro alla fine
                errori.append(f"{g['chiave']}: {e}")
        if errori:
            # il segno non avanza: al giro dopo questi grezzi si ritrasformano, invece di restare fuori in silenzio
            raise RuntimeError(f"{len(errori)} grezzi non trasformati ({fatti} sì): " + "; ".join(errori[:5]))
        segno.write_text(str(inizio))
        return {"trasformati": fatti, "errori": errori[:20]}


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
    d'una, e solo se almeno una è cambiata dal giro prima."""

    def __init__(self, fonte: str, query: dict, funzione, uscita: str, kind: str):
        self.fonte, self.query, self.funzione, self.uscita, self.kind = fonte, query, funzione, uscita, kind

    def __call__(self, ctx) -> dict:
        leg = int(ctx.config["fonti"][self.fonte]["legislatura"])
        lago = Lago(ctx.cartella)
        ultimi = {n: lago.ultimo(self.fonte, camera_ocd.chiave(n, leg)) for n in self.query}
        mancano = [n for n, u in ultimi.items() if not u]
        if mancano:
            raise RuntimeError(f"mancano nel lago: {mancano}")
        impronta = "-".join(u["impronta"][:8] for u in ultimi.values())
        uscita = ctx.cartella / "uscite" / "v3" / self.fonte / f"leg{leg}-{self.uscita}.jsonl"
        segno = ctx.cartella / "uscite" / f".{self.fonte}.impronta"
        if uscita.exists() and segno.exists() and segno.read_text() == impronta:
            return {"trasformati": 0, "motivo": "dati invariati"}
        grezzi = {n: json.loads(lago.leggi(u["file"])) for n, u in ultimi.items()}
        r = self.funzione(grezzi, leg, {"chiave": f"leg{leg}-{self.uscita}", "impronta": impronta})
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
        inizio, fatti, errori = time.time(), 0, []
        basi = sorted({re.sub(r"-allegati$", "", g["chiave"]) for g in lago.nuovi_dal(fonte, da) if re.search(r"-c\w+(-allegati)?$", g["chiave"])})
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
        if errori:
            raise RuntimeError(f"{len(errori)} comunicati non trasformati ({fatti} sì): " + "; ".join(errori[:5]))
        segno.write_text(str(inizio))
        return {"trasformati": fatti}


class TrasformaDossier:
    """Scheda e testo di un dossier insieme, con i metadati presi dagli elenchi (data, servizio, nota)."""

    def __call__(self, ctx) -> dict:
        fonte = camera_dossier.NOME
        lago, uscita = Lago(ctx.cartella), ctx.cartella / "uscite" / "v3" / fonte
        segno = ctx.cartella / "uscite" / f".{fonte}.ultimo"
        da = float(segno.read_text()) if segno.exists() else 0.0
        inizio, fatti, errori = time.time(), 0, []
        schede = [g for g in lago.nuovi_dal(fonte, da) if g["chiave"].endswith("-scheda")]
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
        if errori:
            raise RuntimeError(f"{len(errori)} dossier non trasformati ({fatti} sì): " + "; ".join(errori[:5]))
        segno.write_text(str(inizio))
        return {"trasformati": fatti}


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
    Passo("trasforma_senato_osr", TrasformaInsieme("senato_osr", senato_osr.QUERY, senato_anagrafica.trasforma, "anagrafica", "anagrafica"),
          dopo=["scarica_senato_osr"], timeout_minuti=10),
    Passo("trasforma_corrispondenze", trasforma_corrispondenze, dopo=["scarica_camera_ocd", "scarica_senato_osr"], timeout_minuti=10),
    Passo("scarica_senato_ddl", senato_ddl.scarica, timeout_minuti=20, tentativi=1),
    Passo("trasforma_senato_ddl", TrasformaInsieme("senato_ddl", {"ddl": "", "firmatari": "", "presentatori": ""}, senato_ddl_t.trasforma, "atti", "atti"),
          dopo=["scarica_senato_ddl"], timeout_minuti=10),
    Passo("scarica_senato_aic", camera_aic.scarica_senato, timeout_minuti=60, tentativi=2),
    Passo("trasforma_senato_aic", Trasforma("senato_aic", camera_aic_t.trasforma_senato, chiavi=r"-aic-\d{6}$"), dopo=["scarica_senato_aic"], timeout_minuti=20),
    Passo("scarica_senato_resoconti", senato_resoconti.scarica, timeout_minuti=10, tentativi=1),
    Passo("scarica_senato_akn", senato_akn.scarica, timeout_minuti=120, tentativi=2),
    Passo("trasforma_senato_resoconti", Trasforma("senato_resoconti", senato_resoconto.trasforma, chiavi=r"-senato-sed\d+$"),
          dopo=["scarica_senato_resoconti", "scarica_senato_akn"], timeout_minuti=60),
    Passo("trasforma_senato_sommari", Trasforma("senato_akn", senato_sommario.trasforma, chiavi=r"-senato-som-", segno="senato_akn_sommari"),
          dopo=["scarica_senato_akn"], timeout_minuti=60),
    Passo("trasforma_senato_testi", Trasforma("senato_akn", senato_testi.trasforma, chiavi=r"-senato-testo-", segno="senato_akn_testi"),
          dopo=["scarica_senato_akn"], timeout_minuti=60),
    Passo("trasforma_senato_emendamenti", Trasforma("senato_akn", senato_emendamenti.trasforma, chiavi=r"-senato-eme-", segno="senato_akn_emendamenti"),
          dopo=["scarica_senato_akn"], timeout_minuti=60),
    Passo("scarica_senato_voti", senato_voti.scarica, timeout_minuti=60, tentativi=1),
    Passo("trasforma_senato_voti", Trasforma("senato_voti", senato_voti_t.trasforma, chiavi=r"-senato-voti-sed"), dopo=["scarica_senato_voti"], timeout_minuti=30),
    Passo("scarica_camera_voti", camera_voti.scarica, timeout_minuti=120, tentativi=2),
    Passo("trasforma_camera_voti", Trasforma("camera_voti", camera_voti_t.trasforma, chiavi="-voti-sed"), dopo=["scarica_camera_voti"], timeout_minuti=60),
    Passo("scarica_eurovoc", eurovoc.scarica, timeout_minuti=10, tentativi=2),
    Passo("trasforma_eurovoc", Trasforma("eurovoc", eurovoc_t.trasforma), dopo=["scarica_eurovoc"], timeout_minuti=5),
    Passo("controlla_uscite", controlli_uscite.controlla, dopo=["trasforma_eurovoc", "trasforma_camera_resoconti", "trasforma_camera_ocd", "trasforma_camera_governo", "trasforma_camera_atti", "trasforma_camera_voti",
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
    Passo("carica_postgres", postgres.carica, dopo=["controlla_uscite"], timeout_minuti=120, critico=True),
    Passo("raccogli_vettori", vettori.passo_raccogli, timeout_minuti=60, tentativi=2),
    Passo("taglia_brani", vettori.passo_taglia, dopo=["carica_postgres"], timeout_minuti=60),
    Passo("invia_vettori", vettori.passo_invia, dopo=["taglia_brani", "raccogli_vettori"], timeout_minuti=60, tentativi=2),
]
