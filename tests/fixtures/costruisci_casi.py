"""Costruisce i casi di prova (casi_costruiti.json) dai dati di tests/fixtures/dati-hf.

Ogni caso parte da una citazione vera, esatta, e cambia una cosa sola: deve
fallire con l'esito indicato, e solo con quello. In coda alcuni controlli
positivi (citazioni che devono passare).

    python tests/fixtures/costruisci_casi.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parents[1]))

from verifica.dati import DatiHF  # noqa: E402
from verifica.identificatori import link_camera, uri_gruppo  # noqa: E402

CAMERA = "http://dati.camera.it/ocd/persona.rdf/"
GR = "http://dati.camera.it/ocd/gruppoParlamentare.rdf/"
CGM = "http://dati.camera.it/ocd/componenteGruppoMisto.rdf/"

# Basi: citazioni esatte delle risposte vere
FDI = {  # Fratelli d'Italia, 30/11/2022
    "speaker": CAMERA + "p305688", "group": GR + "gr4133",
    "speech": "leg19_sed16_tit00040.sub00020.int00180",
    "quote": "la prima risoluzione su questo tema è stata presentata dal sottoscritto",
}
MAGI = {  # +Europa, componente del Misto
    "speaker": CAMERA + "p307436", "group": CGM + "cgm4139",
    "speech": "leg19_sed690_tit00090.int00090",
    "quote": "siccome secondo noi è una legge antidemocratica, plebiscitaria",
}
DURIGON = {  # sottosegretario, parla per il Governo
    "speaker": "gov_durigon_claudio", "government": True,
    "speech": "leg19_sed15_tit00070.sub00020.int00020",
    "quote": "per gli Stati che, invece, non sono obbligati ad introdurre un salario minimo legale",
}
NM = {  # Noi Moderati
    "speaker": CAMERA + "p300447", "group": GR + "gr4152",
    "speech": "leg19_sed209_tit00080.int00410",
    "quote": "sapete, colleghi, c'è solo un problema",
}
IV_PRIMA = {  # nel gruppo Azione-Italia Viva fino al 20/11/2023
    "speaker": CAMERA + "p306005", "group": GR + "gr4135",
    "speech": "leg19_sed24_tit00090.sub00050.int00080",
    "quote": "Coloro che definirono le dichiarazioni delle Nazioni Unite non scrissero qui sì e lì no",
}


def con(base: dict, **modifiche) -> dict:
    claim = dict(base)
    for k, v in modifiche.items():
        if v is None:
            claim.pop(k, None)
        else:
            claim[k] = v
    if "link" not in modifiche:
        claim["link"] = link_camera(claim["speech"]) or ""
    return claim


SED16 = "https://www.camera.it/leg19/410?idSeduta=0016&tipo=stenografico"


def casi() -> list:
    sed16 = SED16
    return [
        # intervento_inesistente
        ("intervento che non c'è in una seduta presente", "intervento_inesistente", "speech_not_in_sitting",
         con(FDI, speech="leg19_sed16_tit00040.sub00020.int99990", link=sed16)),
        ("seduta che non c'è nei dati", "intervento_inesistente", "sitting_not_in_data",
         con(FDI, speech="leg19_sed9999_tit00010.int00010",
             link="https://www.camera.it/leg19/410?idSeduta=9999&tipo=stenografico")),
        ("intervento del Senato su dati della sola Camera", "intervento_inesistente", "sitting_not_in_data",
         con(FDI, speech="sen_leg19_sed100_p1103_deb1_0",
             link="https://www.senato.it/show-doc?leg=19&tipodoc=Resaula&id=1387468&idoggetto=0")),
        ("ID di un chunk al posto dell'intervento", "intervento_inesistente", "speech_not_in_sitting",
         con(FDI, speech=FDI["speech"] + "_chunk_4", link=link_camera(FDI["speech"]))),
        ("intervento di un'altra legislatura", "intervento_inesistente", "sitting_not_in_data",
         con(FDI, speech="leg18_sed100_tit00010.int00010",
             link="https://www.camera.it/leg18/410?idSeduta=0100&tipo=stenografico")),
        # non_trovata
        ("una parola cambiata", "non_trovata", "not_in_speech_text",
         con(FDI, quote=FDI["quote"].replace("presentata", "depositata"))),
        ("punteggiatura cambiata", "non_trovata", "not_in_speech_text",
         con(MAGI, quote=MAGI["quote"].replace(", plebiscitaria", "; plebiscitaria"))),
        ("parole saltate con i puntini", "non_trovata", "not_in_speech_text",
         con(MAGI, quote="siccome secondo noi è una legge antidemocratica … che toglie ogni forza alla libertà")),
        ("citazione tradotta", "non_trovata", "not_in_speech_text",
         con(FDI, quote="the first resolution on this issue was presented by me")),
        ("virgolette doppie cambiate", "non_trovata", "not_in_speech_text",
         con(IV_PRIMA, quote="Scrissero: «universali». Il principio vale per tutti")),
        # parole_di_terzi
        ("impegno citato tra «» dall'oratore", "parole_di_terzi", "inside_quotation_marks",
         con(FDI, speaker=CAMERA + "p306352", group=GR + "gr4131",
             speech="leg19_sed418_tit00080.sub00020.int00040",
             quote="impegna il Governo ad adoperarsi per la convocazione di una conferenza sulla sicurezza in Europa")),
        ("citazione che si apre con le virgolette del resoconto", "parole_di_terzi", "opens_with_quotation_marks",
         con(FDI, speaker=CAMERA + "p306352", group=GR + "gr4131",
             speech="leg19_sed418_tit00080.sub00020.int00040",
             quote="«impegna il Governo ad adoperarsi per la convocazione di una conferenza")),
        ("parole di una collega riportate dall'oratore", "parole_di_terzi", "attributed_to_someone_else",
         con(FDI, speaker=CAMERA + "p307790", group=None,
             speech="leg19_sed440_tit00060.sub00220.int00060",
             quote="siamo al ventitreesimo mese di calo della produzione industriale")),
        ("frase tra “” nel resoconto", "parole_di_terzi", "inside_quotation_marks",
         con(FDI, speaker=CAMERA + "p308840", group=None,
             speech="leg19_sed489_tit00070.sub00010.int00060",
             quote="Sono quello che il mio Paese definisce un'eccellenza, va bene così")),
        ("domande riportate tra “”", "parole_di_terzi", "inside_quotation_marks",
         con(FDI, speaker=CAMERA + "p307822", group=None,
             speech="leg19_sed489_tit00070.sub00010.int00100",
             quote="Perché non fai ricerca?")),
        # oratore_errato
        ("un altro deputato dello stesso gruppo", "oratore_errato", "different_speaker",
         con(FDI, speaker=CAMERA + "p308910")),
        ("un deputato di un altro gruppo, con il suo gruppo", "oratore_errato", "different_speaker",
         con(FDI, speaker=CAMERA + "p302069", group=GR + "gr4136")),
        ("un altro membro del Governo", "oratore_errato", "different_speaker",
         con(DURIGON, speaker="gov_calderone_marina_elvira")),
        ("un senatore", "oratore_errato", "different_speaker",
         con(FDI, speaker="http://dati.senato.it/senatore/1103")),
        ("una persona che non esiste", "oratore_errato", "different_speaker",
         con(FDI, speaker=CAMERA + "p999999")),
        # gruppo_errato
        ("un altro gruppo", "gruppo_errato", "other_group_on_date",
         con(FDI, group=GR + "gr4136")),
        ("il Misto al posto della componente", "gruppo_errato", "misto_instead_of_component",
         con(MAGI, group=GR + "gr4111")),
        ("un'altra componente del Misto", "gruppo_errato", "other_group_on_date",
         con(MAGI, group=CGM + "cgm4271")),
        ("al Governo senza esserci", "gruppo_errato", "not_in_government_on_date",
         con(FDI, group=None, government=True)),
        ("il gruppo di dopo, non quello alla data", "gruppo_errato", "other_group_on_date",
         con(IV_PRIMA, group=GR + "gr4211")),
        # link_errato
        ("un'altra seduta", "link_errato", "wrong_sitting",
         con(FDI, link="https://www.camera.it/leg19/410?idSeduta=0017&tipo=stenografico")),
        ("la pagina della seduta, non il resoconto", "link_errato", "not_the_record",
         con(FDI, link="https://www.camera.it/leg19/410?idSeduta=0016&tipo=seduta")),
        ("il sito del Senato per un intervento della Camera", "link_errato", "wrong_site",
         con(FDI, link="https://www.senato.it/show-doc?leg=19&tipodoc=Resaula&id=1387468")),
        ("ancora su un altro intervento", "link_errato", "wrong_anchor",
         con(FDI, link=sed16 + "#sed0016.stenografico.tit00040.sub00020.int00200")),
        ("un'altra legislatura", "link_errato", "wrong_page",
         con(FDI, link="https://www.camera.it/leg18/410?idSeduta=0016&tipo=stenografico")),
    ]


def positivi() -> list:
    return [
        ("alla lettera", "esatta", con(FDI, quote="La prima risoluzione su questo tema è stata presentata dal sottoscritto")),
        ("maiuscola iniziale cambiata", "esatta_dopo_normalizzazione", con(FDI)),
        ("a capo e spazi doppi", "esatta_dopo_normalizzazione",
         con(MAGI, quote="siccome secondo noi è una legge\nantidemocratica,  plebiscitaria")),
        ("apostrofo tipografico al posto di quello del resoconto", "esatta_dopo_normalizzazione",
         con(NM, quote=NM["quote"].replace("c'è", "c’è"))),
        ("componente del Misto", "esatta_dopo_normalizzazione", con(MAGI)),
        ("membro del Governo", "esatta_dopo_normalizzazione", con(DURIGON)),
        ("link senza ancora", "esatta_dopo_normalizzazione", con(FDI, link="https://www.camera.it/leg19/410?idSeduta=16&tipo=stenografico")),
        ("ancora sul dibattito", "esatta_dopo_normalizzazione", con(FDI, link=SED16 + "#sed0016.stenografico.tit00040")),
        ("URI con https", "esatta_dopo_normalizzazione", con(FDI, speaker=FDI["speaker"].replace("http://", "https://"))),
        ("gruppo con il nome di allora", "esatta", con(IV_PRIMA)),
    ]


def main() -> None:
    dati = DatiHF(QUI / "dati-hf")
    out = {"cases": [], "controls": []}
    for nome, esito, motivo, claim in casi():
        if "group" not in claim and not claim.get("government"):
            # Il gruppo della persona, dai dati: il caso cambia una cosa sola
            gruppi = [a for a in dati.appartenenze(claim["speaker"]) if a.org_type == "group"]
            claim["group"] = uri_gruppo(gruppi[-1].name, "camera")
        out["cases"].append({"name": nome, "outcome": esito, "reason": motivo, "claim": claim})
    for nome, esito, claim in positivi():
        out["controls"].append({"name": nome, "outcome": esito, "claim": claim})
    (QUI / "casi_costruiti.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out['cases'])} casi, {len(out['controls'])} controlli")


if __name__ == "__main__":
    main()
