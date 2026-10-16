"""Fase 2: riga di comando e rapporto Markdown."""
import json

from conftest import FIXTURES, RISPOSTE
from verifica.cli import main

DATI = str(FIXTURES / "dati-hf")


def test_riga_di_comando_markdown(capsys):
    path = FIXTURES / "risposte" / "fascicoli-e7db466f.json"
    assert main([str(path), "--dati", DATI]) == 1
    out = capsys.readouterr().out
    assert out.startswith("Verifica ParliamentRAG v0.1.0 · dati 2026-09-03 (emeierkeio/parliamentrag-leg19@fa656621)")
    assert "Citazioni   10 su 11 esatte" in out
    assert "✗ #1  gruppo_errato:" in out
    assert "~ 10 esatte dopo normalizzazione (maiuscola iniziale): #2," in out


def test_riga_di_comando_json_uguale_alla_libreria(capsys):
    path = FIXTURES / "risposte" / "fascicoli-e81bde33.json"
    assert main([str(path), "--dati", DATI, "--json", "-"]) == 0
    r = json.loads(capsys.readouterr().out)
    atteso = json.loads((FIXTURES / "rapporti" / path.name).read_text())
    assert r == atteso


def test_formato_sbagliato(tmp_path, capsys):
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"schema": "x", "claims": []}))
    assert main([str(f), "--dati", DATI]) == 2
    assert "non segue il formato v1" in capsys.readouterr().err


def test_json_non_valido(tmp_path, capsys):
    f = tmp_path / "r.json"
    f.write_text("{")
    assert main([str(f), "--dati", DATI]) == 2


def test_tutte_le_risposte_da_riga_di_comando(capsys):
    for path in RISPOSTE:
        assert main([str(path), "--dati", DATI]) in (0, 1)
