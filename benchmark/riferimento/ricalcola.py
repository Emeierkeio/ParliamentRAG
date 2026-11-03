#!/usr/bin/env python3
"""Riesegue le query delle risposte di riferimento e dice quali risultati sono cambiati.

Uso, dalla cartella piattaforma:
    python3 benchmark/riferimento/ricalcola.py              # solo confronto
    python3 benchmark/riferimento/ricalcola.py APP-022 ...  # solo questi id
    python3 benchmark/riferimento/ricalcola.py --mostra     # stampa anche i risultati nuovi
    python3 benchmark/riferimento/ricalcola.py --scrivi     # sovrascrive risultato e controllato_su

Ogni query gira in una transazione BEGIN READ ONLY ... ROLLBACK su Postgres v3
(docker compose exec -T testi psql). Solo libreria standard.

Come si lega una query al risultato salvato:
- risultato è un elenco e c'è una sola query: la query dà l'elenco;
- risultato è un oggetto con tante chiavi quante query: la query n dà la chiave n;
- risultato è un elenco di elenchi, uno per query: la query n dà l'elemento n;
- un elenco lungo può essere salvato ridotto, {"righe_totali": n, "righe": [...]}:
  si confrontano il numero di righe e le prime righe;
- negli altri casi il legame non è certo: lo script dice se il risultato salvato
  (o ogni sua chiave) coincide con il risultato di una delle query, altrimenti
  chiede di rileggerlo a mano; con --scrivi non tocca il file.

Con --scrivi cambiano solo risultato e controllato_su: risposta, stato e limiti
vanno riletti a mano, perché sono testo.
"""

import argparse
import datetime
import json
import pathlib
import subprocess
import sys

CARTELLA = pathlib.Path(__file__).resolve().parent
PIATTAFORMA = CARTELLA.parent.parent
PSQL = ["docker", "compose", "exec", "-T", "testi", "psql", "-U", "parliamentrag",
        "-d", "parliamentrag", "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1"]


def esegui(sql):
    """Esegue una select in sola lettura e torna l'elenco delle righe come dizionari."""
    corpo = sql.strip().rstrip(";")
    testo = ("BEGIN READ ONLY;\n"
             "SELECT coalesce(json_agg(t), '[]'::json) FROM (\n" + corpo + "\n) t;\n"
             "ROLLBACK;\n")
    r = subprocess.run(PSQL, input=testo, capture_output=True, text=True, cwd=PIATTAFORMA)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return json.loads(r.stdout)


def normalizza(x):
    """Rende confrontabili numeri scritti come 1, 1.0 o 1.00."""
    if isinstance(x, dict):
        return {k: normalizza(v) for k, v in x.items()}
    if isinstance(x, list):
        return [normalizza(v) for v in x]
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def uguali(a, b):
    return normalizza(a) == normalizza(b)


def stessa_insieme(a, b):
    """Stesse righe in ordine diverso."""
    if not (isinstance(a, list) and isinstance(b, list)) or len(a) != len(b):
        return False
    chiave = lambda r: json.dumps(normalizza(r), sort_keys=True, ensure_ascii=False)
    return sorted(map(chiave, a)) == sorted(map(chiave, b))


def descrivi(vecchio, nuovo):
    if isinstance(vecchio, list) and isinstance(nuovo, list):
        if stessa_insieme(vecchio, nuovo):
            return "stesse righe, ordine diverso"
        return f"righe {len(vecchio)} -> {len(nuovo)}"
    return "valore diverso"


def troncato(x):
    """Risultato salvato in forma ridotta: {"righe_totali": n, "righe": prime righe}."""
    return isinstance(x, dict) and set(x) == {"righe_totali", "righe"}


def adatta(vecchio, nuovo):
    """Porta le righe nuove nella forma del valore salvato (intera o ridotta)."""
    if troncato(vecchio) and isinstance(nuovo, list):
        return {"righe_totali": len(nuovo), "righe": nuovo[:len(vecchio["righe"])]}
    return nuovo


def componi(salvato, legame):
    """Rimette i risultati nuovi nella forma di quello salvato."""
    if None in legame:
        return adatta(salvato, legame[None])
    if isinstance(salvato, dict):
        return {k: adatta(salvato[k], legame[k]) for k in salvato}
    return [adatta(salvato[i], legame[i]) for i in range(len(salvato))]


def controlla(percorso, args):
    d = json.loads(percorso.read_text())
    salvato = d["risultato"]
    risultati = []
    for i, sql in enumerate(d["sql"], 1):
        try:
            risultati.append(esegui(sql))
        except RuntimeError as e:
            print(f"{d['id']}: errore nella query {i}: {e.splitlines()[0]}")
            return "errore"

    if (isinstance(salvato, list) or troncato(salvato)) and len(risultati) == 1:
        legame = {None: risultati[0]}
    elif isinstance(salvato, dict) and not troncato(salvato) and len(salvato) == len(risultati):
        legame = dict(zip(salvato.keys(), risultati))
    elif (isinstance(salvato, list) and len(salvato) == len(risultati) > 1
          and all(isinstance(x, list) or troncato(x) for x in salvato)):
        legame = {i: r for i, r in enumerate(risultati)}
    else:
        legame = None

    if legame is None:
        if any(uguali(salvato, r) for r in risultati) or (
                isinstance(salvato, dict) and not troncato(salvato)
                and all(any(uguali(v, adatta(v, r)) for r in risultati) for v in salvato.values())):
            print(f"{d['id']}: invariato (legame query-risultato non certo)")
            return "invariato"
        print(f"{d['id']}: da rileggere a mano: risultato salvato diverso da ogni query "
              f"({len(risultati)} query, legame non certo)")
        if args.mostra:
            print(json.dumps(risultati, ensure_ascii=False, indent=1))
        return "incerto"

    cambi = []
    for chiave, nuovo in legame.items():
        vecchio = salvato if chiave is None else salvato[chiave]
        nuovo = adatta(vecchio, nuovo)
        if not uguali(vecchio, nuovo):
            if troncato(vecchio):
                vecchio, nuovo = vecchio["righe"], nuovo["righe"]
            cambi.append((chiave, descrivi(vecchio, nuovo)))
    if not cambi:
        print(f"{d['id']}: invariato")
        return "invariato"

    for chiave, come in cambi:
        etichetta = "" if chiave is None else (f" [query {chiave + 1}]" if isinstance(chiave, int) else f" [{chiave}]")
        print(f"{d['id']}: cambiato{etichetta}: {come}")
    if args.mostra:
        print(json.dumps(componi(salvato, legame), ensure_ascii=False, indent=1))
    if args.scrivi:
        d["risultato"] = componi(salvato, legame)
        d["controllato_su"] = f"postgres v3 {datetime.date.today().isoformat()} (ricalcola.py)"
        testo = percorso.read_text()
        rientro = 2 if testo.startswith('{\n  "') else 1
        nuovo_testo = json.dumps(d, ensure_ascii=False, indent=rientro)
        percorso.write_text(nuovo_testo + ("\n" if testo.endswith("\n") else ""))
        print(f"{d['id']}: scritto, rileggere risposta, stato e limiti")
    return "cambiato"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("id", nargs="*", help="id da controllare (default: tutti)")
    p.add_argument("--scrivi", action="store_true", help="sovrascrive risultato quando il legame è certo")
    p.add_argument("--mostra", action="store_true", help="stampa i risultati nuovi")
    args = p.parse_args()

    file = sorted(CARTELLA.glob("*.json"))
    if args.id:
        file = [f for f in file if f.stem in set(args.id)]
    conti = {}
    for f in file:
        esito = controlla(f, args)
        conti[esito] = conti.get(esito, 0) + 1
    print("\n" + ", ".join(f"{k} {v}" for k, v in sorted(conti.items())))
    return 1 if conti.get("errore") else 0


if __name__ == "__main__":
    sys.exit(main())
