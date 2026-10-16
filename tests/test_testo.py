"""Regole sul testo e sui link, senza dati."""
from verifica.identificatori import chiave_nome, controlla_link, da_chunk, link_camera, uri_gruppo
from verifica.testo import parole_di_terzi, trova


def test_solo_tre_differenze_ammesse():
    testo = "Signor Presidente, noi siamo contrari all'idea di un salario minimo legale."
    assert trova("noi siamo contrari", testo).letterale
    assert trova("Noi siamo contrari", testo).regole == ("first_letter_case",)
    assert trova("noi  siamo\ncontrari", testo).regole == ("whitespace",)
    assert trova("Noi  siamo contrari", testo).regole == ("whitespace", "first_letter_case")
    assert trova("noi siamo contrari all’idea", testo).regole == ("typographic_apostrophe",)
    assert trova("Noi  siamo contrari all’idea", testo).regole == ("whitespace", "first_letter_case", "typographic_apostrophe")
    assert trova("noi siamo contrari all“idea", testo) is None  # virgoletta doppia: no
    assert trova("noi siamo contrari all'idea di un salario minimo legale!", testo) is None
    assert trova("noi siamo … contrari", testo) is None
    assert trova("NOI SIAMO", testo) is None  # solo la prima lettera


def test_parole_di_terzi():
    t = "Il collega Rossi ha detto che il salario minimo è inutile. Noi diciamo «basta tasse» da anni."
    r = trova("il salario minimo è inutile", t)
    assert parole_di_terzi("il salario minimo è inutile", t, r.inizio) == "attributed_to_someone_else"
    r = trova("basta tasse", t)
    assert parole_di_terzi("basta tasse", t, r.inizio) == "inside_quotation_marks"
    r = trova("Noi diciamo", t)
    assert parole_di_terzi("Noi diciamo", t, r.inizio) is None
    assert parole_di_terzi("«basta tasse", t, trova("«basta tasse", t).inizio) == "opens_with_quotation_marks"


def test_virgoletta_mai_chiusa_non_rende_tutto_di_terzi():
    t = "Parere favorevole con riformulazione: “a valutare. Sull'ordine del giorno n. 5 parere “contrario”. Noi votiamo sì."
    assert parole_di_terzi("Noi votiamo sì", t, trova("Noi votiamo sì", t).inizio) is None


def test_link_camera():
    sid = "leg19_sed15_tit00070.sub00020.int00020"
    assert controlla_link(link_camera(sid), sid) == (True, "ok")
    assert controlla_link("https://www.camera.it/leg19/410?idSeduta=0015&tipo=stenografico#sed0015.stenografico.tit00070", sid)[0]
    assert controlla_link("https://www.camera.it/leg19/410?idSeduta=0016&tipo=stenografico", sid) == (False, "wrong_sitting")
    assert controlla_link("ftp://camera.it", sid) == (False, "not_a_url")


def test_link_senato():
    sid = "sen_leg19_sed321_p16725_deb0_5"
    giusto = "https://www.senato.it/show-doc?leg=19&tipodoc=Resaula&id=1462302&idoggetto=0"
    assert controlla_link(giusto, sid) == (True, "ok_format_only")
    assert controlla_link(giusto, sid, resoconto_seduta=giusto) == (True, "ok")
    assert controlla_link(giusto.replace("1462302", "1"), sid, resoconto_seduta=giusto) == (False, "wrong_sitting")
    assert controlla_link("https://www.senato.it/lavori/assemblea/resoconti-elenco-cronologico", sid)[0] is False


def test_nomi_dei_gruppi():
    assert chiave_nome("Italia Viva - Casa Riformista") == chiave_nome("ITALIA VIVA-CASA RIFORMISTA (IV-CR)")
    assert uri_gruppo("ITALIA VIVA-CASA RIFORMISTA (IV-CR)", "camera").endswith("gr4211")
    assert uri_gruppo("Italia Viva - Casa Riformista", "senato") == "http://dati.senato.it/gruppo/91"
    assert uri_gruppo("FRATELLI D'ITALIA").endswith("gr4133")
    assert uri_gruppo("Fratelli d'Italia") == "http://dati.senato.it/gruppo/85"
    assert uri_gruppo("Italia Viva - Il Centro - Renew Europe", "camera").endswith("gr4211")


def test_chunk_e_intervento():
    assert da_chunk("leg19_sed15_tit00070.sub00020.int00020_chunk_4") == "leg19_sed15_tit00070.sub00020.int00020"


def test_apostrofi_ammessi_in_entrambi_i_sensi():
    from verifica.testo import APOSTROFI
    assert set(APOSTROFI) == set("\u2019\u2018\u201b\u02bc\u2032\u0060\u00b4")
    for c in APOSTROFI:
        assert trova(f"c{c}è un problema", "Sapete, c'è un problema.").regole == ("typographic_apostrophe",)
    assert trova("c'è un problema", "Sapete, c’è un problema.").regole == ("typographic_apostrophe",)
    r = trova("c’è un problema", "Il collega Rossi ha detto che c'è un problema.")
    from verifica.testo import parole_di_terzi
    assert parole_di_terzi("c’è un problema", "Il collega Rossi ha detto che c'è un problema.", r.inizio)
