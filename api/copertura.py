"""Copertura del dominio parlamentare: quanto di ciò che Camera e Senato pubblicano è scaricato e modellato.

L'elenco sta in `copertura.toml`, alla radice del repo, e si aggiorna con il codice. Qui si calcola la percentuale
(ogni voce pesa da 1 a 3; fatto = 1, parziale = mezzo, manca = 0; una voce che il ramo non pubblica non conta) e, per le
voci che hanno una query, si contano le righe nel database: una voce data per fatta senza righe si vede nel pannello.
"""

from __future__ import annotations

import time
import tomllib
from pathlib import Path

import psycopg

from .db import connessione

FILE = Path(__file__).resolve().parent.parent / "copertura.toml"
RAMI = ("camera", "senato", "parlamento")
VALE = {"fatto": 1.0, "parziale": 0.5, "manca": 0.0}
OGNI = 3600                                    # i conteggi cambiano di notte: si rifanno ogni ora

_elenco: tuple[float, dict] = (0.0, {})
_righe: tuple[float, dict] = (0.0, {})


def elenco() -> dict:
    """Il file, riletto solo se è cambiato."""
    global _elenco
    m = FILE.stat().st_mtime
    if m != _elenco[0]:
        _elenco = (m, tomllib.loads(FILE.read_text(encoding="utf-8")))
    return _elenco[1]


def stati(voce: dict) -> dict[str, str]:
    """Lo stato della voce per ogni ramo che la riguarda."""
    return {r: voce[r] for r in RAMI if r in voce}


def query(voce: dict, ramo: str) -> str | None:
    q = voce.get(f"conta_{ramo}") or (voce.get("conta") if ramo != "parlamento" or "{ramo}" not in voce.get("conta", "") else None)
    return q.replace("{ramo}", f"'{ramo}'") if q else None


def _conta() -> dict:
    """Le righe nel database per voce e ramo; None se la query non riesce (tabella che manca, tempo scaduto)."""
    global _righe
    if time.monotonic() - _righe[0] < OGNI and _righe[1]:
        return _righe[1]
    out: dict[str, int | None] = {}
    try:
        with connessione() as c:
            for v in elenco().get("voce", []):
                for ramo in stati(v):
                    q = query(v, ramo)
                    if not q:
                        continue
                    try:
                        with c.transaction():       # una query fallita non ferma le altre
                            out[f"{v['nome']}|{ramo}"] = int(c.execute(q).fetchone()["count"])
                    except psycopg.Error:
                        out[f"{v['nome']}|{ramo}"] = None
    except psycopg.Error:
        return _righe[1]
    _righe = (time.monotonic(), out)
    return out


def calcola(voci: list[dict], righe: dict | None = None) -> dict:
    """Percentuale pesata, in tutto e per ramo e area, e le voci una per una con stato, motivo e righe."""
    righe = righe or {}
    somma: dict[str, list[float]] = {}

    def aggiungi(chiave: str, peso: float, valore: float) -> None:
        s = somma.setdefault(chiave, [0.0, 0.0])
        s[0] += peso * valore
        s[1] += peso

    conti = {"fatto": 0, "parziale": 0, "manca": 0}
    fuori = []
    for v in voci:
        peso, riga = float(v.get("peso", 1)), {"area": v["area"], "nome": v["nome"], "peso": v.get("peso", 1), "rami": {}}
        for ramo, stato in stati(v).items():
            n = righe.get(f"{v['nome']}|{ramo}")
            riga["rami"][ramo] = {"stato": stato, "perche": v.get(f"perche_{ramo}") or (v.get("perche") if stato != "fatto" else None),
                                  "righe": n, "vuoto": stato == "fatto" and n == 0}
            if stato not in VALE:
                continue                            # il ramo non lo pubblica
            conti[stato] += 1
            for chiave in ("tutto", f"ramo:{ramo}", f"area:{v['area']}"):
                aggiungi(chiave, peso, VALE[stato])
        fuori.append(riga)
    quota = {k: round(100 * a / b, 1) if b else None for k, (a, b) in somma.items()}
    return {"percento": quota.get("tutto"), "rami": {r: quota[f"ramo:{r}"] for r in RAMI if f"ramo:{r}" in quota},
            "aree": {k[5:]: q for k, q in quota.items() if k.startswith("area:")}, "conti": conti, "voci": fuori}


def copertura() -> dict:
    try:
        e = elenco()
    except (OSError, tomllib.TOMLDecodeError) as x:
        return {"errore": type(x).__name__}
    return {**calcola(e.get("voce", []), _conta()), "verificato": str(e.get("verificato", ""))}
