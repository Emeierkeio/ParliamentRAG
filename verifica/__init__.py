"""parliamentrag-verifica: controlla una risposta sul Parlamento con i dati aperti.

    from verifica import verifica
    rapporto = verifica(risposta, "./leg19")

`risposta` è un dict nel formato schema/verifiable-answer.v1.json; `dati` è
una cartella con il dataset emeierkeio/parliamentrag-leg19 (vedi
verifica.dati.scarica) oppure una fonte con gli stessi metodi di
verifica.dati.DatiHF. Il risultato segue schema/report.v1.json.

Questa versione controlla le citazioni. Gruppi e autorevolezza arrivano
nelle fasi successive del piano (docs/piano-verifica.md).
"""
from __future__ import annotations

__version__ = "0.1.0"


def verifica(risposta: dict, dati) -> dict:
    from .dati import DatiHF
    from .formato import valida
    from .rapporto import crea

    fonte = DatiHF(dati) if isinstance(dati, (str, bytes)) or hasattr(dati, "__fspath__") else dati
    return crea(valida(risposta), fonte, __version__)
