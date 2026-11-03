"""python -m pipeline giro | riprendi [id] | stato [id] | passo <nome>"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

from .orchestra import Stato, giro
from .passi import PASSI

QUI = Path(__file__).resolve().parent.parent


def main(argv: list[str]) -> int:
    config = tomllib.loads((QUI / "pipeline.toml").read_text())
    cartella = (QUI / config["giro"]["cartella_dati"]).resolve()
    cmd = argv[0] if argv else "giro"
    if cmd == "giro":
        r = giro(PASSI, config, cartella)
    elif cmd == "riprendi":
        # si riprendono solo i passi di quel giro: un giro lanciato con «passo» non diventa un giro completo
        st = Stato(cartella / "stato.sqlite")
        g = argv[1] if len(argv) > 1 else st.ultimo_giro()
        r = giro(PASSI, config, cartella, g, solo={nome for nome, *_ in st.passi_del_giro(g)} or None)
    elif cmd == "passo":
        r = giro(PASSI, config, cartella, solo=set(argv[1:]))
    elif cmd == "stato":
        st = Stato(cartella / "stato.sqlite")
        g = argv[1] if len(argv) > 1 else st.ultimo_giro()
        for nome, esito, t, ini, fine, riep, err in st.passi_del_giro(g):
            print(f"{nome:32} {esito:9} tentativo {t}  {riep[:120]}  {err[-160:] if err else ''}")
        return 0
    else:
        print(__doc__)
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["esito"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
