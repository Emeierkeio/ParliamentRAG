"""Fase 1: controllo delle citazioni su risposte vere e su casi costruiti."""
import json

import pytest

from conftest import FIXTURES, RISPOSTE, carica
from verifica import __version__, verifica
from verifica.citazioni import ESITI
from verifica.rapporto import crea

# Le citazioni delle risposte vere che non risultano esatte sui dati pubblicati
# del 3/9/2026, e perché. "dati": difetto del dataset di quella data, già
# corretto nel grafo (la release successiva lo porta). "fascicoli": difetto vero
# della risposta. Una citazione che cambia esito fa fallire il test: va
# guardata, non aggiunta qui senza capire.
GOVERNO_MANCANTE = "il dataset del 3/9 non ha gli incarichi di governo dei ministri e sottosegretari deputati; il grafo sì"
SPIEGAZIONI = {
    ("fascicoli-06447f37", 1): ("gruppo_errato", "dati", "Freni, sottosegretario: " + GOVERNO_MANCANTE),
    ("fascicoli-90540f01", 1): ("gruppo_errato", "dati", "Meloni, Presidente del Consiglio: " + GOVERNO_MANCANTE),
    ("fascicoli-a211e6f3", 1): ("gruppo_errato", "dati", "Tajani, ministro: " + GOVERNO_MANCANTE),
    ("fascicoli-b25b1599", 1): ("gruppo_errato", "dati", "Ferrante, sottosegretario: " + GOVERNO_MANCANTE),
    ("fascicoli-e7db466f", 1): ("gruppo_errato", "dati", "Giorgetti, ministro: " + GOVERNO_MANCANTE),
    ("fascicoli-2326bfaa", 1): ("oratore_errato", "dati",
                                "il dataset del 3/9 attribuisce l'intervento all'omonimo Tommaso Calderone; "
                                "nel grafo è di Marina Calderone (corretto il 14/10)"),
    ("fascicoli-98a96566", 1): ("oratore_errato", "dati",
                                "nel dataset del 3/9 l'intervento è del nodo doppio di Bellucci (p307426), "
                                "poi unito a gov_bellucci_maria_teresa nel grafo"),
    ("fascicoli-4c15c581", 1): ("non_trovata", "fascicoli",
                                "il resoconto ha «anche no . Ma»: la citazione toglie lo spazio prima del punto"),
    **{("fascicoli-57c3caca", n): ("non_trovata", "fascicoli", "risposta in inglese con la citazione tradotta")
       for n in range(1, 10)},
}


@pytest.fixture(scope="module")
def rapporti(dati):
    return {p.stem: verifica(carica(p), dati) for p in RISPOSTE}


def test_risposte_vere_esatte_o_spiegate(rapporti):
    trovati = {}
    for nome, r in rapporti.items():
        for v in r["quotes"]["items"]:
            if v["outcome"] not in ("esatta", "esatta_dopo_normalizzazione"):
                trovati[(nome, v["index"])] = v["outcome"]
    assert trovati == {k: v[0] for k, v in SPIEGAZIONI.items()}


def test_conteggio_sulle_venti(rapporti):
    totale = sum(r["quotes"]["total"] for r in rapporti.values())
    esatte = sum(r["quotes"]["exact"] for r in rapporti.values())
    assert (totale, esatte) == (180, 163)
    assert sum(1 for v in SPIEGAZIONI.values() if v[1] == "fascicoli") == 10


@pytest.mark.parametrize("path", RISPOSTE, ids=lambda p: p.stem)
def test_rapporto_identico_a_quello_atteso(path, dati):
    """Stessa risposta, stessi dati, stessa versione: stesso rapporto, byte per byte."""
    atteso = (FIXTURES / "rapporti" / path.name).read_text(encoding="utf-8")
    r = verifica(carica(path), dati)
    assert json.dumps(r, ensure_ascii=False, indent=1) + "\n" == atteso


def test_rapporto_dice_versioni(rapporti):
    r = next(iter(rapporti.values()))
    assert r["verifier"] == {"name": "parliamentrag-verifica", "version": __version__}
    assert r["data"]["version"] == "2026-09-03"
    assert r["data"]["revision"] == "fa6566217075741f4100eb1994b90db885c09904"
    assert r["warnings"][0]["code"] == "data_version_differs"


CASI = carica(FIXTURES / "casi_costruiti.json")
BASE = {"schema": "https://w3id.org/parliamentrag/verify/v1", "system": {"name": "test"},
        "question": "domanda", "data_version": "2026-09-03"}


def test_trenta_casi_costruiti_coprono_tutti_gli_esiti_negativi():
    assert len(CASI["cases"]) == 30
    assert {c["outcome"] for c in CASI["cases"]} == set(ESITI) - {"esatta", "esatta_dopo_normalizzazione"}


@pytest.mark.parametrize("caso", CASI["cases"], ids=lambda c: c["name"])
def test_caso_costruito_fallisce_con_l_esito_giusto(caso, dati):
    v = verifica({**BASE, "claims": [caso["claim"]]}, dati)["quotes"]["items"][0]
    assert v["outcome"] == caso["outcome"]
    assert caso["reason"] in v["reasons"].values()


@pytest.mark.parametrize("caso", CASI["controls"], ids=lambda c: c["name"])
def test_controllo_positivo_passa(caso, dati):
    v = verifica({**BASE, "claims": [caso["claim"]]}, dati)["quotes"]["items"][0]
    assert v["outcome"] == caso["outcome"]


def test_nessuna_citazione(dati):
    r = verifica({**BASE, "claims": []}, dati)
    assert r["quotes"] == {"total": 0, "exact": 0, "by_outcome": {}, "not_verifiable": {}, "items": []}


def test_crea_non_dipende_dall_ora(dati):
    risposta = carica(RISPOSTE[0])
    assert crea(risposta, dati, "x") == crea(risposta, dati, "x")
