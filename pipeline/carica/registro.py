"""Registro del caricamento: quali file delle uscite sono già in un database, con quale impronta, e quali sono in
quarantena (non passano i controlli o non si caricano).

Sta in `caricamento.sqlite`, nella cartella dei dati, separato per destinazione (il Postgres locale o quello indicato
da PGHOST): lo stesso file caricato in locale va ancora caricato su un database remoto. Per riconoscere un file
invariato bastano data di modifica e dimensione; se cambiano si ricalcola l'impronta del contenuto.

La quarantena non è definitiva: a ogni giro i file in quarantena si ricontrollano e si riprovano. Serve a non fermare
gli altri file e a dire nel riepilogo quali sono rimasti fuori e perché.

Prima del registro il caricamento teneva un solo segno (`uscite/.postgres.ultimo`, l'ora dell'ultimo caricamento
riuscito): un file più vecchio di quel segno e non ancora nel registro vale come già caricato.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path


def impronta_file(f: Path) -> str:
    h = hashlib.sha256()
    with f.open("rb") as x:
        for blocco in iter(lambda: x.read(1 << 20), b""):
            h.update(blocco)
    return h.hexdigest()


class Registro:
    def __init__(self, cartella: Path, destinazione: str):
        self.radice = cartella / "uscite" / "v3"
        self.destinazione = destinazione
        cartella.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(cartella / "caricamento.sqlite", timeout=60)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS caricati (destinazione TEXT, percorso TEXT, impronta TEXT, ns INTEGER, byte INTEGER,
                quando REAL, PRIMARY KEY (destinazione, percorso));
            CREATE TABLE IF NOT EXISTS quarantena (destinazione TEXT, percorso TEXT, impronta TEXT, fase TEXT, motivo TEXT,
                quando REAL, giro TEXT, PRIMARY KEY (destinazione, percorso));
            CREATE TABLE IF NOT EXISTS meta (destinazione TEXT, chiave TEXT, valore TEXT, PRIMARY KEY (destinazione, chiave));
        """)
        segno = cartella / "uscite" / ".postgres.ultimo"
        # il segno vecchio vale solo per il database locale, l'unico in cui il caricamento di prima scriveva
        self.segno_vecchio = float(segno.read_text()) if destinazione == "locale" and segno.exists() else 0.0

    def rel(self, f: Path) -> str:
        return str(f.relative_to(self.radice))

    def da_caricare(self, f: Path) -> str | None:
        """L'impronta del file se va caricato; None se nella destinazione c'è già questa versione."""
        st, rel = f.stat(), self.rel(f)
        r = self.db.execute("SELECT impronta, ns, byte FROM caricati WHERE destinazione = ? AND percorso = ?", (self.destinazione, rel)).fetchone()
        if r and r[1] == st.st_mtime_ns and r[2] == st.st_size:
            return None
        h = impronta_file(f)
        if r and r[0] == h:                                   # riscritto uguale: si aggiorna solo la data
            self._scrivi_caricato(rel, h, st)
            return None
        if not r and st.st_mtime < self.segno_vecchio:
            self._scrivi_caricato(rel, h, st)
            return None
        return h

    def _scrivi_caricato(self, rel: str, h: str, st) -> None:
        self.db.execute("INSERT INTO caricati VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (destinazione, percorso) DO UPDATE SET "
                        "impronta = excluded.impronta, ns = excluded.ns, byte = excluded.byte, quando = excluded.quando",
                        (self.destinazione, rel, h, st.st_mtime_ns, st.st_size, time.time()))
        self.db.execute("DELETE FROM quarantena WHERE destinazione = ? AND percorso = ?", (self.destinazione, rel))
        self.db.commit()

    def caricato(self, f: Path, h: str) -> None:
        self._scrivi_caricato(self.rel(f), h, f.stat())

    def in_quarantena(self, f: Path, h: str, fase: str, motivo: str, giro: str = "") -> None:
        self.db.execute("INSERT INTO quarantena VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (destinazione, percorso) DO UPDATE SET "
                        "impronta = excluded.impronta, fase = excluded.fase, motivo = excluded.motivo, quando = excluded.quando, giro = excluded.giro",
                        (self.destinazione, self.rel(f), h, fase, motivo[:2000], time.time(), giro))
        self.db.commit()

    def esci_di_quarantena(self, f: Path, fase: str | None = None) -> None:
        q = "DELETE FROM quarantena WHERE destinazione = ? AND percorso = ?" + (" AND fase = ?" if fase else "")
        self.db.execute(q, (self.destinazione, self.rel(f), *([fase] if fase else [])))
        self.db.commit()

    def quarantena_di(self, f: Path) -> dict | None:
        r = self.db.execute("SELECT impronta, fase, motivo FROM quarantena WHERE destinazione = ? AND percorso = ?",
                            (self.destinazione, self.rel(f))).fetchone()
        return dict(zip(("impronta", "fase", "motivo"), r)) if r else None

    def quarantena(self) -> list[dict]:
        return [dict(zip(("percorso", "fase", "motivo", "giro"), r)) for r in self.db.execute(
            "SELECT percorso, fase, motivo, giro FROM quarantena WHERE destinazione = ? ORDER BY percorso", (self.destinazione,))]

    def leggi(self, chiave: str) -> str:
        r = self.db.execute("SELECT valore FROM meta WHERE destinazione = ? AND chiave = ?", (self.destinazione, chiave)).fetchone()
        return r[0] if r else ""

    def scrivi(self, chiave: str, valore: str) -> None:
        self.db.execute("INSERT INTO meta VALUES (?, ?, ?) ON CONFLICT (destinazione, chiave) DO UPDATE SET valore = excluded.valore",
                        (self.destinazione, chiave, valore))
        self.db.commit()
