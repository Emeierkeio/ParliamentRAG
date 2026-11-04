"""python -m pipeline giro [--forza] | riprendi [id] | stato [id] | passo <nome>… | salute | avvisa [--dal T] [--uscita N] [--log F]

giro      un giro completo; si rifiuta (uscita 3) se un giro completo è riuscito nelle ultime 20 ore, salvo --forza
salute    uscita 0 se c'è un giro completo riuscito nelle ultime 26 ore, 1 se no (per un controllo esterno)
avvisa    dopo un giro (pipeline/notte.sh): una mail a segnalazioni@parliamentrag.it se l'esito non è ok
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import tomllib
from pathlib import Path

from .orchestra import Stato, giro

QUI = Path(__file__).resolve().parent.parent
RIFIUTATO = 3          # uscita di «giro» rifiutato perché ce n'è già uno recente: non è un errore
ORE_FRA_GIRI = 20
ORE_SALUTE = 26


def _prove(config: dict, cartella: Path, passi: list) -> list:
    """Controlli prima del primo passo: spazio libero sul disco dei dati e, se un passo usa Postgres, il database."""
    minimo = float(config["giro"].get("spazio_minimo_gb", 5))

    def spazio():
        libero = shutil.disk_usage(cartella).free / 1e9
        if libero < minimo:
            raise RuntimeError(f"{libero:.1f} GB liberi in {cartella}, ne servono almeno {minimo:g}")

    prove = [("prova_spazio", spazio)]
    if any(p.usa_db for p in passi):
        from .carica.postgres import prova
        prove.append(("prova_database", prova))
    return prove


def _opzione(argv: list[str], nome: str, predefinito: str = "") -> str:
    return argv[argv.index(nome) + 1] if nome in argv and argv.index(nome) + 1 < len(argv) else predefinito


def main(argv: list[str]) -> int:
    config = tomllib.loads((QUI / "pipeline.toml").read_text())
    cartella = (QUI / config["giro"]["cartella_dati"]).resolve()
    cartella.mkdir(parents=True, exist_ok=True)
    cmd = argv[0] if argv else "giro"
    if cmd == "salute":
        u = Stato(cartella / "stato.sqlite").ultimo_riuscito()
        if u and time.time() - u["fine"] < ORE_SALUTE * 3600:
            print(f"ok: giro {u['id']} riuscito il {time.strftime('%Y-%m-%d %H:%M', time.localtime(u['fine']))}")
            return 0
        print(f"nessun giro completo riuscito nelle ultime {ORE_SALUTE} ore" + (f" (l'ultimo: {u['id']})" if u else ""))
        return 1
    if cmd == "avvisa":
        from .avvisi import avvisa
        return avvisa(cartella, float(_opzione(argv, "--dal", "0")), int(_opzione(argv, "--uscita", "0")), _opzione(argv, "--log"))
    if cmd == "stato":
        st = Stato(cartella / "stato.sqlite")
        g = argv[1] if len(argv) > 1 else st.ultimo_giro()
        for nome, esito, t, ini, fine, riep, err in st.passi_del_giro(g):
            print(f"{nome:32} {esito:9} tentativo {t}  {riep[:120]}  {err[-160:] if err else ''}")
        return 0
    from .passi import PASSI
    if cmd == "giro":
        u = Stato(cartella / "stato.sqlite").ultimo_riuscito()
        if u and time.time() - u["fine"] < ORE_FRA_GIRI * 3600 and "--forza" not in argv:
            print(f"giro rifiutato: il giro {u['id']} è riuscito meno di {ORE_FRA_GIRI} ore fa (--forza per lanciarlo comunque)")
            return RIFIUTATO
        r = giro(PASSI, config, cartella, prove=_prove(config, cartella, PASSI))
    elif cmd == "riprendi":
        # si riprendono solo i passi di quel giro: un giro lanciato con «passo» non diventa un giro completo
        st = Stato(cartella / "stato.sqlite")
        g = argv[1] if len(argv) > 1 else st.ultimo_giro()
        solo = {nome for nome, *_ in st.passi_del_giro(g) if not nome.startswith("prova_")} or None
        r = giro(PASSI, config, cartella, g, solo=solo, tipo="riprendi",
                 prove=_prove(config, cartella, [p for p in PASSI if not solo or p.nome in solo]))
    elif cmd == "passo":
        solo = set(argv[1:])
        r = giro(PASSI, config, cartella, solo=solo, tipo="passo", prove=_prove(config, cartella, [p for p in PASSI if p.nome in solo]))
    else:
        print(__doc__)
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["esito"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
