"""Orchestratore del giro notturno: passi con dipendenze, limiti di tempo, ripresa e stato in SQLite.

Un passo è una funzione con un nome, i passi da cui dipende e un tempo massimo. Il giro esegue i passi
in ordine topologico; un passo parte solo se tutti quelli da cui dipende sono riusciti. Se un passo
fallisce, si fermano solo i passi che ne dipendono: gli altri rami del giro vanno avanti.

Ogni giro ha un id; lo stato di ogni passo sta in `stato.sqlite`. `riprendi` rilancia un giro
saltando i passi già riusciti.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
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


@dataclass
class Contesto:
    giro: str
    cartella: Path          # cartella dei dati: lago, uscite, stato
    config: dict
    riepiloghi: dict        # riepiloghi dei passi già finiti, per nome

    def log(self, msg: str) -> None:
        print(f"{time.strftime('%H:%M:%S')} [{self.giro}] {msg}", flush=True)


class Stato:
    """Stato dei giri e dei passi in SQLite: sopravvive ai crolli e dice dove riprendere."""

    def __init__(self, file: Path):
        file.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(file)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS giri (id TEXT PRIMARY KEY, inizio REAL, fine REAL, esito TEXT);
            CREATE TABLE IF NOT EXISTS passi (giro TEXT, nome TEXT, inizio REAL, fine REAL, esito TEXT,
                tentativo INTEGER, riepilogo TEXT, errore TEXT, PRIMARY KEY (giro, nome));
        """)

    def apri_giro(self, giro: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO giri VALUES (?, ?, NULL, 'in_corso')", (giro, time.time()))
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


def _in_processo(fai, ctx, coda):
    try:
        coda.put(("ok", fai(ctx) or {}))
    except BaseException:  # l'errore completo torna al processo principale e finisce nello stato
        coda.put(("errore", traceback.format_exc()))


_IN_CORSO: list = []  # il processo del passo in corso, da fermare se si ferma il giro


def _ferma(segnale, _frame):
    """Se il giro riceve SIGTERM o SIGINT, ferma anche il passo in corso: altrimenti continuerebbe da solo."""
    for p in _IN_CORSO:
        if p.is_alive():
            p.terminate()
            p.join(5)
    raise SystemExit(128 + segnale)


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
        p.terminate()
        p.join(5)
        return "timeout", {}, f"superati {passo.timeout_minuti} minuti"
    if coda.empty():
        return "errore", {}, f"processo uscito con codice {p.exitcode} senza risultato"
    esito, valore = coda.get()
    return ("ok", valore, "") if esito == "ok" else ("errore", {}, valore)


def ordina(passi: list[Passo]) -> list[Passo]:
    per_nome = {p.nome: p for p in passi}
    for p in passi:
        for d in p.dopo:
            if d not in per_nome:
                raise ValueError(f"il passo {p.nome} dipende da {d}, che non esiste")
    ordinati, visti, in_visita = [], set(), set()

    def visita(p: Passo):
        if p.nome in visti:
            return
        if p.nome in in_visita:
            raise ValueError(f"dipendenza circolare su {p.nome}")
        in_visita.add(p.nome)
        for d in p.dopo:
            visita(per_nome[d])
        in_visita.discard(p.nome)
        visti.add(p.nome)
        ordinati.append(p)

    for p in passi:
        visita(p)
    return ordinati


class Lucchetto:
    """Un solo giro alla volta. Il lucchetto contiene il pid: se quel processo non c'è più, è scaduto e si riprende."""

    def __init__(self, file: Path):
        self.file = file

    def __enter__(self):
        if self.file.exists():
            try:
                pid = int(self.file.read_text().strip())
                os.kill(pid, 0)
                raise RuntimeError(f"un giro è già in corso (pid {pid})")
            except (ProcessLookupError, ValueError):
                pass  # lucchetto di un giro morto: si sovrascrive
        self.file.write_text(str(os.getpid()))
        return self

    def __exit__(self, *a):
        self.file.unlink(missing_ok=True)


def giro(passi: list[Passo], config: dict, cartella: Path, id_giro: str | None = None, solo: set[str] | None = None) -> dict:
    """Esegue (o riprende, se id_giro esiste già) un giro. Restituisce l'esito per passo."""
    cartella.mkdir(parents=True, exist_ok=True)
    stato = Stato(cartella / "stato.sqlite")
    id_giro = id_giro or stato.nuovo_id()  # un id esistente vuol dire riprendere quel giro, quindi uno nuovo non deve mai coincidere
    limite = time.time() + float(config.get("giro", {}).get("timeout_minuti", 300)) * 60
    esiti: dict[str, str] = {}
    signal.signal(signal.SIGTERM, _ferma)
    signal.signal(signal.SIGINT, _ferma)
    with Lucchetto(cartella / "giro.lock"):
        stato.apri_giro(id_giro)
        fatti = stato.riusciti(id_giro)
        ctx = Contesto(id_giro, cartella, config, dict(fatti))
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
            if time.time() > limite:
                esiti[p.nome] = "saltato"
                stato.segna(id_giro, p.nome, "saltato", errore="tempo del giro finito")
                continue
            for t in range(1, p.tentativi + 1):
                ctx.log(f"inizio {p.nome} (tentativo {t}/{p.tentativi})")
                stato.segna(id_giro, p.nome, "in_corso", t)
                esito, riepilogo, errore = esegui_passo(p, ctx)
                stato.segna(id_giro, p.nome, esito, t, riepilogo, errore)
                ctx.log(f"fine {p.nome}: {esito} {json.dumps(riepilogo, ensure_ascii=False, default=str)[:300]}")
                if esito == "ok":
                    ctx.riepiloghi[p.nome] = riepilogo
                    break
                if t < p.tentativi:
                    time.sleep(min(60 * t, 300))
            esiti[p.nome] = esito
        falliti_critici = [p.nome for p in passi if p.critico and not esiti.get(p.nome, "").startswith("ok")]
        complessivo = "ok" if all(e.startswith("ok") for e in esiti.values()) else ("bloccato" if falliti_critici else "parziale")
        stato.chiudi_giro(id_giro, complessivo)
    return {"giro": id_giro, "esito": complessivo, "passi": esiti}
