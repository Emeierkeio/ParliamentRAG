"""Fotografia della macchina e del giro notturno per il pannello /sistema (api/sistema.py): `python -m pipeline sistema`.

Il container web non vede la VPS: questo comando, dal cron ogni 10 minuti, scrive dati/sistema/stato.json con i giri
(stato.sqlite), i file in quarantena (caricamento.sqlite), disco, memoria, carico, container, backup e versione del
codice. Niente segreti nel file: solo nomi, numeri ed esiti. Ciò che manca (in locale non c'è docker né il backup)
resta vuoto.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

GIRI = 60
LOG_BACKUP = Path("/var/log/parliamentrag-backup.log")


def _sql(file: Path, query: str) -> list[dict]:
    if not file.exists():
        return []
    with sqlite3.connect(f"file:{file}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        return [dict(r) for r in db.execute(query)]


def _comando(*args: str) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _avviso(riepilogo: str | None) -> str | None:
    try:
        r = json.loads(riepilogo or "{}")
    except ValueError:
        return None
    a = r.get("avviso") if isinstance(r, dict) else None
    return ("; ".join(map(str, a)) if isinstance(a, list) else str(a))[:300] if a else None


def giri(cartella: Path) -> dict:
    f = cartella / "stato.sqlite"
    elenco = _sql(f, f"""
        SELECT g.id, g.inizio, g.fine, g.esito, g.tipo,
               sum(p.esito = 'ok') AS ok, sum(p.esito = 'errore') AS errori, sum(p.esito = 'saltato') AS saltati, count(p.nome) AS passi
        FROM giri g LEFT JOIN passi p ON p.giro = g.id GROUP BY g.id ORDER BY g.inizio DESC LIMIT {GIRI}""")
    ultimo = next((g for g in elenco if g["tipo"] == "giro"), elenco[0] if elenco else None)
    passi = []
    if ultimo:
        for p in _sql(f, f"SELECT nome, inizio, fine, esito, tentativo, riepilogo, errore FROM passi WHERE giro = '{ultimo['id']}' ORDER BY inizio"):
            passi.append({"nome": p["nome"], "esito": p["esito"], "tentativo": p["tentativo"],
                          "secondi": round(p["fine"] - p["inizio"]) if p["fine"] and p["inizio"] else None,
                          "avviso": _avviso(p["riepilogo"]), "errore": (p["errore"] or "")[-300:] or None})
    return {"elenco": elenco, "ultimo": ultimo, "passi": passi}


def quarantena(cartella: Path) -> list[dict]:
    return _sql(cartella / "caricamento.sqlite",
                "SELECT percorso, fase, substr(motivo, 1, 300) AS motivo, quando, giro FROM quarantena ORDER BY quando DESC")


def macchina(cartella: Path) -> dict:
    disco = shutil.disk_usage(cartella)
    m = {"disco": {"totale": disco.total, "usato": disco.used, "libero": disco.free}}
    try:
        mem = {k: int(v.split()[0]) * 1024 for k, v in (r.split(":", 1) for r in Path("/proc/meminfo").read_text().splitlines())}
        m["memoria"] = {"totale": mem["MemTotal"], "disponibile": mem["MemAvailable"],
                        "swap_totale": mem.get("SwapTotal", 0), "swap_libero": mem.get("SwapFree", 0)}
        m["carico"] = [float(x) for x in Path("/proc/loadavg").read_text().split()[:3]]
        m["acceso_da"] = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, KeyError, ValueError):
        pass
    m["cpu"] = os.cpu_count()
    return m


def container() -> list[dict]:
    righe = _comando("docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}\t{{.State}}")
    return [dict(zip(("nome", "stato", "attivo"), r.split("\t"))) for r in righe.splitlines() if r.count("\t") == 2]


def backup() -> dict:
    if not LOG_BACKUP.exists():
        return {}
    righe = LOG_BACKUP.read_text(errors="replace").splitlines()[-3000:]
    ultime = [r for r in righe if re.match(r"\d{4}-\d{2}-\d{2} ", r)][-12:]
    return {"righe": ultime, "fallito": any("FALLITO" in r for r in ultime[-6:])}


def scrivi(cartella: Path) -> Path:
    radice = cartella.parent
    stato = {"scritto": time.time(), "giri": giri(cartella), "quarantena": quarantena(cartella),
             "macchina": macchina(cartella), "container": container(), "backup": backup(),
             "codice": {"commit": _comando("git", "-C", str(radice), "log", "-1", "--format=%h %cI %s")}}
    uscita = cartella / "sistema" / "stato.json"
    uscita.parent.mkdir(parents=True, exist_ok=True)
    tmp = uscita.with_suffix(".tmp")
    tmp.write_text(json.dumps(stato, ensure_ascii=False, indent=1))
    tmp.replace(uscita)                      # il web non legge mai un file a metà
    return uscita
