"""Orchestratore del giro notturno: passi con dipendenze, limiti di tempo, ripresa e stato in SQLite.

Un passo è una funzione con un nome, i passi da cui dipende e un tempo massimo. Il giro esegue i passi
in ordine topologico; un passo parte solo se tutti quelli da cui dipende sono riusciti. Se un passo
fallisce, si fermano solo i passi che ne dipendono: gli altri rami del giro vanno avanti.

Ogni giro ha un id; lo stato di ogni passo sta in `stato.sqlite`. `riprendi` rilancia un giro
saltando i passi già riusciti.

Un passo che chiama un sito (`sito = "camera"`) e riceve 403 o 503 ferma gli altri passi dello stesso sito per quel
giro: la Camera blocca l'IP e insistere allunga il blocco. I passi con `limite_giro = False` (trasformazioni,
controlli, caricamento) partono anche se i download hanno finito il tempo del giro.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import re
import signal
import sqlite3
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class Passo:
    nome: str
    fai: Callable[["Contesto"], dict | None]   # restituisce un riepilogo (conteggi, file scritti)
    dopo: list[str] = field(default_factory=list)
    timeout_minuti: float = 30
    tentativi: int = 1
    critico: bool = False                       # se fallisce, il giro non pubblica
    dopo_comunque: list[str] = field(default_factory=list)   # passi che vengono prima, ma che non bloccano se falliscono
    sito: str = ""                              # sito chiamato: dopo un blocco (403/503) i passi dello stesso sito si saltano
    limite_giro: bool = True                    # False: parte anche a tempo del giro finito (lavoro locale, caricamento)
    usa_db: bool = False                        # legge o scrive Postgres: il giro prova prima il database


@dataclass
class Contesto:
    giro: str
    cartella: Path          # cartella dei dati: lago, uscite, stato
    config: dict
    riepiloghi: dict        # riepiloghi dei passi già finiti, per nome

    def log(self, msg: str) -> None:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{self.giro}] {msg}", flush=True)


class Stato:
    """Stato dei giri e dei passi in SQLite: sopravvive ai crolli e dice dove riprendere."""

    def __init__(self, file: Path):
        file.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(file, timeout=60)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS giri (id TEXT PRIMARY KEY, inizio REAL, fine REAL, esito TEXT);
            CREATE TABLE IF NOT EXISTS passi (giro TEXT, nome TEXT, inizio REAL, fine REAL, esito TEXT,
                tentativo INTEGER, riepilogo TEXT, errore TEXT, PRIMARY KEY (giro, nome));
        """)
        if "tipo" not in {r[1] for r in self.db.execute("PRAGMA table_info(giri)")}:
            self.db.execute("ALTER TABLE giri ADD COLUMN tipo TEXT")   # giro | riprendi | passo
            self.db.commit()

    def apri_giro(self, giro: str, tipo: str = "giro") -> None:
        self.db.execute("INSERT OR IGNORE INTO giri (id, inizio, fine, esito, tipo) VALUES (?, ?, NULL, 'in_corso', ?)", (giro, time.time(), tipo))
        self.db.execute("UPDATE giri SET esito = 'in_corso', fine = NULL WHERE id = ?", (giro,))
        self.db.commit()

    def chiudi_giro(self, giro: str, esito: str) -> None:
        self.db.execute("UPDATE giri SET fine = ?, esito = ? WHERE id = ?", (time.time(), esito, giro))
        self.db.commit()

    def segna(self, giro: str, nome: str, esito: str, tentativo: int = 1, riepilogo: dict | None = None, errore: str = "") -> None:
        self.db.execute("""INSERT INTO passi VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (giro, nome) DO UPDATE SET fine = excluded.fine, esito = excluded.esito,
            tentativo = excluded.tentativo, riepilogo = excluded.riepilogo, errore = excluded.errore""",
            (giro, nome, time.time(), time.time() if esito != "in_corso" else None, esito, tentativo,
             json.dumps(riepilogo or {}, ensure_ascii=False, default=str), errore[-4000:]))
        self.db.commit()

    def riusciti(self, giro: str) -> dict[str, dict]:
        rows = self.db.execute("SELECT nome, riepilogo FROM passi WHERE giro = ? AND esito = 'ok'", (giro,))
        return {n: json.loads(r or "{}") for n, r in rows}

    def nuovo_id(self) -> str:
        """Id di un giro nuovo: la data e l'ora, con un suffisso se nello stesso secondo è già partito un altro giro."""
        base, n = time.strftime("%Y%m%d-%H%M%S"), 1
        ident = base
        while self.db.execute("SELECT 1 FROM giri WHERE id = ?", (ident,)).fetchone():
            n += 1
            ident = f"{base}-{n}"
        return ident

    def ultimo_giro(self) -> str | None:
        r = self.db.execute("SELECT id FROM giri ORDER BY inizio DESC LIMIT 1").fetchone()
        return r[0] if r else None

    def passi_del_giro(self, giro: str) -> list[tuple]:
        return self.db.execute("SELECT nome, esito, tentativo, inizio, fine, riepilogo, errore FROM passi WHERE giro = ? ORDER BY inizio", (giro,)).fetchall()

    def giro_info(self, giro: str) -> dict | None:
        r = self.db.execute("SELECT id, inizio, fine, esito, tipo FROM giri WHERE id = ?", (giro,)).fetchone()
        return dict(zip(("id", "inizio", "fine", "esito", "tipo"), r)) if r else None

    def giri_dal(self, da: float) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT id FROM giri WHERE inizio >= ? ORDER BY inizio", (da,))]

    def ultimo_riuscito(self) -> dict | None:
        """L'ultimo giro completo finito con esito ok. I giri di prima della colonna `tipo` contano come completi se
        hanno almeno 40 passi."""
        r = self.db.execute("""SELECT id, fine FROM giri g WHERE esito = 'ok' AND fine IS NOT NULL AND (tipo = 'giro'
            OR (tipo IS NULL AND (SELECT count(*) FROM passi p WHERE p.giro = g.id) >= 40)) ORDER BY fine DESC LIMIT 1""").fetchone()
        return {"id": r[0], "fine": r[1]} if r else None


def _in_processo(fai, ctx, coda):
    signal.signal(signal.SIGTERM, signal.SIG_DFL)   # con fork il figlio erediterebbe _ferma del giro
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        os.setpgrp()   # un gruppo proprio: alla scadenza si fermano anche psql, git e Chromium lanciati dal passo
    except OSError:
        pass
    try:
        coda.put(("ok", fai(ctx) or {}))
    except BaseException:  # l'errore completo torna al processo principale e finisce nello stato
        coda.put(("errore", traceback.format_exc()))


_IN_CORSO: list = []  # il processo del passo in corso, da fermare se si ferma il giro


class Interrotto(SystemExit):
    """Il giro ha ricevuto SIGTERM o SIGINT."""


def _uccidi(p) -> None:
    """Ferma il processo del passo e tutto il suo gruppo: prima SIGTERM, dopo 5 secondi SIGKILL."""
    for segnale in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(p.pid, segnale)
        except (ProcessLookupError, PermissionError, OSError):
            if p.is_alive():                     # il gruppo non c'è ancora (il processo non ha fatto in tempo a crearlo)
                p.terminate() if segnale == signal.SIGTERM else p.kill()
        p.join(5)
        if not p.is_alive():
            try:
                os.killpg(p.pid, signal.SIGKILL)   # i figli rimasti (psql, Chromium) dopo che il passo è uscito
            except (ProcessLookupError, PermissionError, OSError):
                pass
            return


def _ferma(segnale, _frame):
    """Se il giro riceve SIGTERM o SIGINT, ferma anche il passo in corso: altrimenti continuerebbe da solo."""
    for p in _IN_CORSO:
        if p.is_alive():
            _uccidi(p)
    raise Interrotto(128 + segnale)


def esegui_passo(passo: Passo, ctx: Contesto) -> tuple[str, dict, str]:
    """Il passo gira in un processo a parte, così il giro lo termina quando supera il tempo massimo."""
    coda: mp.Queue = mp.Queue()
    p = mp.Process(target=_in_processo, args=(passo.fai, ctx, coda), daemon=True)
    try:
        p.start()
    except Exception:  # il passo non parte (per esempio non si può copiare nel processo): fallisce il passo e il giro continua
        return "errore", {}, traceback.format_exc()
    _IN_CORSO[:] = [p]
    p.join(passo.timeout_minuti * 60)
    if p.is_alive():
        _uccidi(p)
        return "timeout", {}, f"superati {passo.timeout_minuti} minuti"
    if coda.empty():
        return "errore", {}, f"processo uscito con codice {p.exitcode} senza risultato"
    esito, valore = coda.get()
    return ("ok", valore, "") if esito == "ok" else ("errore", {}, valore)


def ordina(passi: list[Passo]) -> list[Passo]:
    per_nome = {p.nome: p for p in passi}
    for p in passi:
        for d in p.dopo + p.dopo_comunque:
            if d not in per_nome:
                raise ValueError(f"il passo {p.nome} dipende da {d}, che non esiste")
    ordinati, visti, in_visita = [], set(), set()

    def visita(p: Passo):
        if p.nome in visti:
            return
        if p.nome in in_visita:
            raise ValueError(f"dipendenza circolare su {p.nome}")
        in_visita.add(p.nome)
        for d in p.dopo + p.dopo_comunque:
            visita(per_nome[d])
        in_visita.discard(p.nome)
        visti.add(p.nome)
        ordinati.append(p)

    for p in passi:
        visita(p)
    return ordinati


class Lucchetto:
    """Un solo giro alla volta. Il lucchetto si crea con O_EXCL (due giri che partono insieme non lo prendono tutti e due)
    e contiene il pid: se quel processo non c'è più, è scaduto e si riprende."""

    def __init__(self, file: Path):
        self.file = file

    def __enter__(self):
        for _ in range(2):
            try:
                fd = os.open(self.file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                try:
                    pid = int(self.file.read_text().strip())
                    os.kill(pid, 0)
                except (ProcessLookupError, ValueError, FileNotFoundError):
                    self.file.unlink(missing_ok=True)       # lucchetto di un giro morto: si toglie e si riprova
                    continue
                except PermissionError:
                    pass                                    # il processo c'è, di un altro utente
                raise RuntimeError(f"un giro è già in corso (pid {pid})")
            with os.fdopen(fd, "w") as f:
                f.write(str(os.getpid()))
            return self
        raise RuntimeError(f"lucchetto {self.file} conteso")

    def __exit__(self, *a):
        self.file.unlink(missing_ok=True)


BLOCCO = re.compile(r"HTTP Error (403|503)|HTTP (403|503)\b|\b(403|503) (Forbidden|Service Unavailable)")


def _avvisi(riepilogo: dict) -> list[str]:
    a = riepilogo.get("avviso") if isinstance(riepilogo, dict) else None
    return [a] if isinstance(a, str) and a else list(a or [])


def giro(passi: list[Passo], config: dict, cartella: Path, id_giro: str | None = None, solo: set[str] | None = None,
         tipo: str = "giro", prove: list[tuple[str, Callable[[], None]]] = ()) -> dict:
    """Esegue (o riprende, se id_giro esiste già) un giro. Restituisce l'esito per passo e gli avvisi.
    `prove` sono controlli fatti prima del primo passo (database raggiungibile, spazio libero): se uno fallisce,
    il giro si chiude subito come «bloccato»."""
    cartella.mkdir(parents=True, exist_ok=True)
    stato = Stato(cartella / "stato.sqlite")
    id_giro = id_giro or stato.nuovo_id()  # un id esistente vuol dire riprendere quel giro, quindi uno nuovo non deve mai coincidere
    limite = time.time() + float(config.get("giro", {}).get("timeout_minuti", 300)) * 60
    esiti: dict[str, str] = {}
    avvisi: list[str] = []
    bloccati: dict[str, str] = {}     # sito -> motivo, dopo un 403 o un 503
    signal.signal(signal.SIGTERM, _ferma)
    signal.signal(signal.SIGINT, _ferma)
    with Lucchetto(cartella / "giro.lock"):
        stato.apri_giro(id_giro, tipo)
        ctx = Contesto(id_giro, cartella, config, {})
        for nome, prova in prove:
            try:
                prova()
            except Exception as e:
                stato.segna(id_giro, nome, "errore", errore=str(e))
                stato.chiudi_giro(id_giro, "bloccato")
                ctx.log(f"giro fermato prima di cominciare: {nome}: {e}")
                return {"giro": id_giro, "esito": "bloccato", "passi": {nome: "errore"}, "avvisi": [f"{nome}: {e}"]}
        fatti = stato.riusciti(id_giro)
        ctx.riepiloghi.update(fatti)
        corrente = None
        try:
            for p in ordina(passi):
                if solo and p.nome not in solo:
                    continue
                if p.nome in fatti:
                    esiti[p.nome] = "ok (già fatto)"
                    continue
                # con `solo`, i passi rimasti fuori dal giro si considerano già fatti
                bloccanti = [d for d in p.dopo if not esiti.get(d, "").startswith("ok") and not (solo and d not in solo)]
                if bloccanti:
                    esiti[p.nome] = "saltato"
                    stato.segna(id_giro, p.nome, "saltato", errore=f"dipende da passi non riusciti: {', '.join(bloccanti)}")
                    ctx.log(f"salto {p.nome}: dipende da {', '.join(bloccanti)}")
                    continue
                if p.sito and p.sito in bloccati:
                    esiti[p.nome] = "saltato"
                    stato.segna(id_giro, p.nome, "saltato", errore=f"{p.sito} ha bloccato un passo prima: {bloccati[p.sito]}")
                    ctx.log(f"salto {p.nome}: {p.sito} ha bloccato ({bloccati[p.sito]})")
                    continue
                if p.limite_giro and time.time() > limite:
                    esiti[p.nome] = "saltato"
                    stato.segna(id_giro, p.nome, "saltato", errore="tempo del giro finito")
                    continue
                corrente = p.nome
                for t in range(1, p.tentativi + 1):
                    ctx.log(f"inizio {p.nome} (tentativo {t}/{p.tentativi})")
                    stato.segna(id_giro, p.nome, "in_corso", t)
                    esito, riepilogo, errore = esegui_passo(p, ctx)
                    stato.segna(id_giro, p.nome, esito, t, riepilogo, errore)
                    ctx.log(f"fine {p.nome}: {esito} {json.dumps(riepilogo, ensure_ascii=False, default=str)[:300]}")
                    if esito == "ok":
                        ctx.riepiloghi[p.nome] = riepilogo
                        avvisi += [f"{p.nome}: {a}" for a in _avvisi(riepilogo)]
                        break
                    m = BLOCCO.search(errore) if p.sito else None
                    if m:
                        bloccati[p.sito] = f"{p.nome}: {m.group(0)}"
                        break                            # niente altri tentativi contro un sito che blocca
                    if t < p.tentativi:
                        time.sleep(min(60 * t, 300))
                corrente = None
                esiti[p.nome] = esito
        except Interrotto:
            if corrente:
                stato.segna(id_giro, corrente, "interrotto", errore="giro fermato da un segnale")
            stato.chiudi_giro(id_giro, "interrotto")
            raise
        falliti_critici = [p.nome for p in passi if p.critico and p.nome in esiti and not esiti[p.nome].startswith("ok")]
        complessivo = "ok" if all(e.startswith("ok") for e in esiti.values()) else ("bloccato" if falliti_critici else "parziale")
        stato.chiudi_giro(id_giro, complessivo)
    return {"giro": id_giro, "esito": complessivo, "passi": esiti, "avvisi": avvisi}
