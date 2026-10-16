"""Fase 0: lo schema valida le risposte vere; il controllo scritto a mano dice lo stesso."""
import copy
import json

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from conftest import FIXTURES, RADICE, RISPOSTE, carica
from verifica.formato import errori

SCHEMA = Draft202012Validator(carica(RADICE / "schema" / "verifiable-answer.v1.json"), format_checker=FormatChecker())
RAPPORTO = Draft202012Validator(carica(RADICE / "schema" / "report.v1.json"), format_checker=FormatChecker())


def test_ci_sono_venti_risposte_vere():
    assert len(RISPOSTE) == 20


@pytest.mark.parametrize("path", RISPOSTE, ids=lambda p: p.stem)
def test_lo_schema_valida_le_risposte_vere(path):
    risposta = carica(path)
    assert list(SCHEMA.iter_errors(risposta)) == []
    assert errori(risposta) == []


def test_lo_schema_valida_i_casi_costruiti():
    casi = carica(FIXTURES / "casi_costruiti.json")
    base = {"schema": "https://w3id.org/parliamentrag/verify/v1", "system": {"name": "test"},
            "question": "q", "data_version": "2026-09-03"}
    for caso in casi["cases"] + casi["controls"]:
        risposta = {**base, "claims": [caso["claim"]]}
        assert list(SCHEMA.iter_errors(risposta)) == [], caso["name"]
        assert errori(risposta) == [], caso["name"]


def _sbagliate():
    buona = carica(RISPOSTE[0])
    claim = buona["claims"][0]
    modifiche = {
        "manca la domanda": lambda r: r.pop("question"),
        "manca la versione dei dati": lambda r: r.pop("data_version"),
        "schema sbagliato": lambda r: r.update(schema="https://example.org/v2"),
        "campo in più": lambda r: r.update(extra=1),
        "ID di persona non ufficiale": lambda r: r["claims"][0].update(speaker="Mario Rossi"),
        "gruppo come nome": lambda r: r["claims"][0].update(group="Fratelli d'Italia"),
        "manca il gruppo": lambda r: r["claims"][0].pop("group", None) or r["claims"][0].pop("government", None),
        "gruppo e governo insieme": lambda r: r["claims"][0].update(group="http://dati.camera.it/ocd/gruppoParlamentare.rdf/gr4133", government=True),
        "speech non è uno speech_id": lambda r: r["claims"][0].update(speech="intervento-123"),
        "manca la citazione": lambda r: r["claims"][0].pop("quote"),
        "camera sconosciuta": lambda r: r.update(chambers=["regione"]),
    }
    assert claim
    for nome, cambia in modifiche.items():
        r = copy.deepcopy(buona)
        cambia(r)
        yield nome, r


@pytest.mark.parametrize("nome,risposta", list(_sbagliate()), ids=lambda x: x if isinstance(x, str) else "")
def test_schema_e_controllo_a_mano_rifiutano_le_stesse(nome, risposta):
    assert list(SCHEMA.iter_errors(risposta)), nome
    assert errori(risposta), nome


@pytest.mark.parametrize("path", sorted((FIXTURES / "rapporti").glob("*.json")), ids=lambda p: p.stem)
def test_i_rapporti_seguono_lo_schema(path):
    assert list(RAPPORTO.iter_errors(carica(path))) == []


def test_gli_esiti_sono_gli_stessi_nello_schema_e_nella_libreria():
    from verifica.citazioni import ESITI
    assert tuple(carica(RADICE / "schema" / "report.v1.json")["$defs"]["outcome"]["enum"]) == ESITI


def test_lo_schema_stesso_e_valido():
    for nome in ("verifiable-answer.v1.json", "report.v1.json"):
        Draft202012Validator.check_schema(json.loads((RADICE / "schema" / nome).read_text()))
