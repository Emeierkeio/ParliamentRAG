"""Segreti e indirizzi dei database: solo da variabili d'ambiente o dal file .env, mai negli argomenti dei comandi."""

from __future__ import annotations

import os
from pathlib import Path

QUI = Path(__file__).resolve().parent.parent


def env(nome: str, predefinito: str | None = None) -> str:
    if nome in os.environ:
        return os.environ[nome]
    f = QUI / ".env"
    if f.exists():
        for riga in f.read_text().splitlines():
            riga = riga.strip()
            if riga and not riga.startswith("#") and "=" in riga:
                k, v = riga.split("=", 1)
                if k.strip() == nome:
                    return v.strip().strip('"').strip("'")
    if predefinito is None:
        raise KeyError(f"manca {nome} in ambiente o in .env")
    return predefinito
