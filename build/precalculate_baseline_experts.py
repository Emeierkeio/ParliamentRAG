"""
Pre-calcola e salva in evaluation_set.json i deputati (con punteggi di autorità)
presenti nel testo baseline di ciascun topic.

Uso:
    python build/precalculate_baseline_experts.py [--base-url http://localhost:8000]

Il backend deve essere in esecuzione. Lo script chiama
    POST /api/history/precalculate-baseline-experts
che legge evaluation_set.json, computa gli esperti e riscrive il file arricchito.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error


def main():
    parser = argparse.ArgumentParser(description="Pre-calcola gli esperti baseline in evaluation_set.json")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="URL base del backend FastAPI (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    url = f"{args.base_url}/api/history/precalculate-baseline-experts"
    print(f"→ POST {url}")

    req = urllib.request.Request(url, method="POST", data=b"", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"[ERRORE] HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERRORE] Impossibile connettersi a {args.base_url}: {e.reason}", file=sys.stderr)
        print("Assicurati che il backend sia in esecuzione.", file=sys.stderr)
        sys.exit(1)

    print(f"✓ Completato:")
    print(f"  Calcolati : {result.get('computed', '?')}")
    print(f"  Saltati   : {result.get('skipped', '?')} (già presenti)")
    print(f"  Totale    : {result.get('total', '?')} topic")
    if result.get("errors"):
        print(f"  Errori    : {result['errors']}", file=sys.stderr)


if __name__ == "__main__":
    main()
