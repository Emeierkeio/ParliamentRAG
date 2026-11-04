"""Lago dei grezzi: ogni file scaricato si salva una volta sola, con fonte, chiave, data e impronta.

I grezzi non si modificano: se la fonte cambia un documento, se ne salva una versione nuova con
un'impronta diversa. Così ogni passo dopo si può rifare dai grezzi senza riscaricare, e si sa sempre
da quale versione della fonte viene un dato. Se la fonte torna a una versione già vista (A, poi B, poi di nuovo A),
A non si riscrive ma prende la data di oggi: l'ultima versione di una chiave è sempre l'ultima vista.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path


class Lago:
    def __init__(self, cartella: Path):
        self.cartella = cartella / "lago"
        self.cartella.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.cartella / "indice.sqlite")
        self.db.execute("""CREATE TABLE IF NOT EXISTS grezzi (fonte TEXT, chiave TEXT, impronta TEXT, url TEXT,
            scaricato REAL, byte INTEGER, file TEXT, PRIMARY KEY (fonte, chiave, impronta))""")
        self.db.commit()

    def salva(self, fonte: str, chiave: str, contenuto: bytes, url: str = "", estensione: str = "bin") -> dict:
        """Salva un grezzo. Se è uguale all'ultima versione, non riscrive e lo dice (`nuovo: False`); se è uguale a una
        versione più vecchia, quella torna l'ultima (`nuovo: True`, perché per chi legge la chiave è cambiata)."""
        impronta = hashlib.sha256(contenuto).hexdigest()
        c = self.db.execute("SELECT file FROM grezzi WHERE fonte = ? AND chiave = ? AND impronta = ?", (fonte, chiave, impronta)).fetchone()
        if c:
            u = self.ultimo(fonte, chiave)
            if u and u["impronta"] == impronta:
                return {"chiave": chiave, "impronta": impronta, "file": c[0], "nuovo": False}
            ora = max(time.time(), (u or {}).get("scaricato") or 0) + 1e-6   # strettamente dopo l'ultima, anche con l'orologio fermo
            self.db.execute("UPDATE grezzi SET scaricato = ? WHERE fonte = ? AND chiave = ? AND impronta = ?", (ora, fonte, chiave, impronta))
            self.db.commit()
            return {"chiave": chiave, "impronta": impronta, "file": c[0], "nuovo": True}
        rel = f"{fonte}/{chiave}/{impronta[:16]}.{estensione}"
        f = self.cartella / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(contenuto)
        tmp.replace(f)  # scrittura atomica: o c'è tutto il file o non c'è
        u = self.ultimo(fonte, chiave)
        ora = max(time.time(), (u["scaricato"] + 1e-6) if u else 0)        # la versione nuova è sempre l'ultima
        self.db.execute("INSERT INTO grezzi VALUES (?, ?, ?, ?, ?, ?, ?)", (fonte, chiave, impronta, url, ora, len(contenuto), rel))
        self.db.commit()
        return {"chiave": chiave, "impronta": impronta, "file": rel, "nuovo": True}

    def ultimo(self, fonte: str, chiave: str) -> dict | None:
        r = self.db.execute("SELECT impronta, file, url, scaricato FROM grezzi WHERE fonte = ? AND chiave = ? ORDER BY scaricato DESC LIMIT 1", (fonte, chiave)).fetchone()
        return {"impronta": r[0], "file": r[1], "url": r[2], "scaricato": r[3]} if r else None

    def leggi(self, rel: str) -> bytes:
        return (self.cartella / rel).read_bytes()

    def chiavi(self, fonte: str) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT DISTINCT chiave FROM grezzi WHERE fonte = ? ORDER BY chiave", (fonte,))]

    def nuovi_dal(self, fonte: str, da: float) -> list[dict]:
        rows = self.db.execute("SELECT chiave, impronta, file, url, scaricato FROM grezzi WHERE fonte = ? AND scaricato >= ? ORDER BY chiave, scaricato", (fonte, da))
        return [dict(zip(("chiave", "impronta", "file", "url", "scaricato"), r)) for r in rows]

    def ultimi_dal(self, fonte: str, da: float) -> list[dict]:
        """Le chiavi con una versione arrivata dopo `da`, ognuna una volta sola con la sua versione più recente."""
        per_chiave = {}
        for g in self.nuovi_dal(fonte, da):        # in ordine di data: vince l'ultima
            per_chiave[g["chiave"]] = g
        return [per_chiave[k] for k in sorted(per_chiave)]

    def righe_prima(self, fonte: str, chiave: str, conta=None) -> int | None:
        """Quante righe ha l'ultima versione di una chiave (un JSON con una lista, o `conta(byte)`); None se non c'è."""
        u = self.ultimo(fonte, chiave)
        if not u:
            return None
        corpo = self.leggi(u["file"])
        return conta(corpo) if conta else len(json.loads(corpo))


def controlla_calo(lago: Lago, fonte: str, chiave: str, righe: int, conta=None, massimo: float = 0.05) -> None:
    """Per le fonti che sostituiscono intere tabelle: una query che perde più del `massimo` delle righe rispetto alla
    versione precedente nel lago non si salva (di solito è l'endpoint a metà, non la fonte che cancella)."""
    prima = lago.righe_prima(fonte, chiave, conta)
    if prima and righe < (1 - massimo) * prima:
        raise RuntimeError(f"{fonte} {chiave}: {righe} righe contro {prima} della versione precedente (calo oltre il {massimo:.0%}): "
                           "non si salva; se il calo è vero, alzare `calo_massimo` della fonte in pipeline.toml per un giro")

    def manifesto(self, fonte: str) -> str:
        return json.dumps([dict(zip(("chiave", "impronta", "url", "scaricato"), r)) for r in self.db.execute(
            "SELECT chiave, impronta, url, scaricato FROM grezzi WHERE fonte = ? ORDER BY chiave", (fonte,))], ensure_ascii=False)
