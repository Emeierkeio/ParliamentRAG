"""Lago dei grezzi: ogni file scaricato si salva una volta sola, con fonte, chiave, data e impronta.

I grezzi non si modificano: se la fonte cambia un documento, se ne salva una versione nuova con
un'impronta diversa. Così ogni passo dopo si può rifare dai grezzi senza riscaricare, e si sa sempre
da quale versione della fonte viene un dato.
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
        """Salva un grezzo. Se la stessa versione c'è già, non riscrive e lo dice (`nuovo: False`)."""
        impronta = hashlib.sha256(contenuto).hexdigest()
        c = self.db.execute("SELECT file FROM grezzi WHERE fonte = ? AND chiave = ? AND impronta = ?", (fonte, chiave, impronta)).fetchone()
        if c:
            return {"chiave": chiave, "impronta": impronta, "file": c[0], "nuovo": False}
        rel = f"{fonte}/{chiave}/{impronta[:16]}.{estensione}"
        f = self.cartella / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(contenuto)
        tmp.replace(f)  # scrittura atomica: o c'è tutto il file o non c'è
        self.db.execute("INSERT INTO grezzi VALUES (?, ?, ?, ?, ?, ?, ?)", (fonte, chiave, impronta, url, time.time(), len(contenuto), rel))
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
        rows = self.db.execute("SELECT chiave, impronta, file, url FROM grezzi WHERE fonte = ? AND scaricato >= ? ORDER BY chiave", (fonte, da))
        return [dict(zip(("chiave", "impronta", "file", "url"), r)) for r in rows]

    def manifesto(self, fonte: str) -> str:
        return json.dumps([dict(zip(("chiave", "impronta", "url", "scaricato"), r)) for r in self.db.execute(
            "SELECT chiave, impronta, url, scaricato FROM grezzi WHERE fonte = ? ORDER BY chiave", (fonte,))], ensure_ascii=False)
