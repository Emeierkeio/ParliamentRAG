"""Riga di comando: parliamentrag-verifica risposta.json --dati ./leg19

Se la cartella dei dati è vuota, scarica il dataset da Hugging Face: la
versione indicata con --versione, altrimenti quella della risposta
(data_version) se esiste come tag o commit del dataset, altrimenti l'ultima.

Stampa il rapporto in Markdown; --json salva anche il rapporto JSON.
Codice di uscita: 0 se tutte le citazioni sono esatte, 1 se qualcuna non lo
è, 2 se la risposta o i dati non si possono leggere.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .dati import DATASET, FILE_NECESSARI, DatiHF, commit_di, scarica
from .formato import FormatoNonValido, valida
from .rapporto import crea, markdown


def _avvisa(msg: str) -> None:
    print(msg, file=sys.stderr)


def _prepara_dati(cartella: Path, versione: str | None, risposta: dict) -> DatiHF:
    if all((cartella / f).exists() for f in FILE_NECESSARI):
        if versione:
            _avvisa(f"uso i dati già presenti in {cartella}: per un'altra versione indica una cartella vuota")
        return DatiHF(cartella)
    revisione = versione
    if revisione is None:
        chiesta = risposta.get("data_version")
        if chiesta and commit_di(chiesta):
            revisione = chiesta
        else:
            revisione = "main"
            if chiesta:
                _avvisa(f"la versione {chiesta} non è pubblicata su Hugging Face: scarico l'ultima")
    scarica(cartella, revisione, DATASET, avvisa=_avvisa)
    return DatiHF(cartella)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="parliamentrag-verifica",
                                description="Controlla le citazioni di una risposta sul Parlamento con i dati aperti.")
    p.add_argument("risposta", help="file JSON nel formato verifiable-answer v1 (- per lo standard input)")
    p.add_argument("--dati", default="./leg19", help="cartella del dataset (scaricato qui se manca)")
    p.add_argument("--versione", help="tag o commit del dataset da scaricare")
    p.add_argument("--json", metavar="FILE", help="salva il rapporto JSON in FILE (- per stamparlo al posto del Markdown)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = p.parse_args(argv)

    try:
        testo = sys.stdin.read() if a.risposta == "-" else Path(a.risposta).read_text(encoding="utf-8")
        risposta = valida(json.loads(testo))
    except FileNotFoundError:
        _avvisa(f"non trovo il file {a.risposta}")
        return 2
    except json.JSONDecodeError as e:
        _avvisa(f"il file non è JSON valido: {e}")
        return 2
    except FormatoNonValido as e:
        _avvisa("la risposta non segue il formato v1:\n- " + "\n- ".join(e.errori))
        return 2

    try:
        fonte = _prepara_dati(Path(a.dati), a.versione, risposta)
    except (OSError, ValueError) as e:
        _avvisa(f"non riesco a preparare i dati: {e}")
        return 2

    r = crea(risposta, fonte, __version__)
    js = json.dumps(r, ensure_ascii=False, indent=2) + "\n"
    if a.json == "-":
        sys.stdout.write(js)
    else:
        if a.json:
            Path(a.json).write_text(js, encoding="utf-8")
        sys.stdout.write(markdown(r))
    q = r["quotes"]
    return 0 if q["exact"] == q["total"] else 1
