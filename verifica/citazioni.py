"""Controllo 1: citazioni esatte.

Per ogni affermazione della risposta, nell'ordine:

1. l'intervento esiste nella versione dei dati;
2. la citazione compare nel testo dell'intervento (alla lettera, oppure con
   le due sole differenze ammesse da testo.py);
3. la citazione appartiene all'oratore, non è una frase di altri che riporta;
4. l'oratore è la persona indicata;
5. il gruppo è quello della persona alla data dell'intervento (per il Misto
   la componente), oppure, se la risposta lo dice, la persona era al Governo;
6. il link porta al resoconto di quella seduta (controllo sul formato e
   sull'ID della seduta, senza scaricare la pagina).

L'esito di ogni citazione è il primo controllo che fallisce; se passano
tutti, `esatta` o `esatta_dopo_normalizzazione`. Il rapporto riporta anche
gli altri controlli, così si vede tutto quello che non va.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from . import identificatori as ids
from .dati import Appartenenza, Fonte, Intervento
from .testo import parole_di_terzi, trova

ESITI = (
    "esatta",
    "esatta_dopo_normalizzazione",
    "non_trovata",
    "parole_di_terzi",
    "oratore_errato",
    "gruppo_errato",
    "link_errato",
    "intervento_inesistente",
)

# Controllo -> esito quando fallisce, nell'ordine in cui si applicano
_ORDINE = (
    ("speech", "intervento_inesistente"),
    ("text", "non_trovata"),
    ("own_words", "parole_di_terzi"),
    ("speaker", "oratore_errato"),
    ("group", "gruppo_errato"),
    ("link", "link_errato"),
)

OK, FAIL, NON_VERIFICABILE, NON_CONTROLLATO = "ok", "fail", "not_verifiable", "not_checked"


def _gruppi_alla_data(apps: List[Appartenenza], data: str, persona: str,
                      camera_intervento: str) -> Tuple[List[dict], List[dict], bool]:
    """Componenti del Misto e gruppi della persona alla data, con l'URI ufficiale.

    Il dataset dà i gruppi per nome. La camera del gruppo, se il dataset non
    la dice, è quella della persona (deputato o senatore) e, per i membri del
    Governo senza seggio, quella dell'intervento.
    """
    camera_persona = ids.camera_della_persona(persona)
    componenti, gruppi = [], []
    for a in apps:
        if not a.valida_il(data):
            continue
        if a.org_type == "misto_component":
            componenti.append({"uri": a.uri, "name": a.name})
        elif a.org_type == "group":
            camera = a.chamber or camera_persona
            u = a.uri or ids.uri_gruppo(a.name, camera) or (None if camera else ids.uri_gruppo(a.name, camera_intervento))
            gruppi.append({"uri": u, "name": a.name})
    al_governo = any(a.org_type == "government" and a.valida_il(data) for a in apps)
    return componenti, gruppi, al_governo


def controlla_gruppo(claim: dict, intervento: Intervento, apps: List[Appartenenza]) -> Tuple[str, str, dict]:
    """(stato, motivo, cosa dicono i dati) per il gruppo indicato nella citazione."""
    data = intervento.date
    if not data:
        return NON_VERIFICABILE, "speech_has_no_date", {}
    componenti, gruppi, al_governo = _gruppi_alla_data(apps, data, claim.get("speaker") or "", intervento.chamber)
    trovato = {"components": componenti, "groups": gruppi, "government": al_governo}
    if claim.get("government"):
        return (OK, "in_government_on_date", trovato) if al_governo else (FAIL, "not_in_government_on_date", trovato)

    indicato = ids.uri(claim.get("group"))
    if not componenti and not gruppi:
        return NON_VERIFICABILE, "no_membership_on_date", trovato
    uri_componenti = {ids.uri(c["uri"]) for c in componenti if c["uri"]}
    uri_gruppi = {ids.uri(g["uri"]) for g in gruppi if g["uri"]}
    if componenti:
        if indicato in uri_componenti:
            return OK, "misto_component_on_date", trovato
        if ids.e_il_misto(indicato) and indicato in uri_gruppi:
            return FAIL, "misto_instead_of_component", trovato
    elif indicato in uri_gruppi:
        return OK, "group_on_date", trovato
    senza_uri = any(not c["uri"] for c in componenti) or any(not g["uri"] for g in gruppi)
    if senza_uri:
        return NON_VERIFICABILE, "membership_without_uri", trovato
    return FAIL, "other_group_on_date", trovato


def controlla(indice: int, claim: dict, intervento: Optional[Intervento], fonte: Fonte,
              sedute_presenti: Optional[set] = None) -> dict:
    """Il risultato del controllo su una citazione."""
    checks: Dict[str, str] = {nome: NON_CONTROLLATO for nome, _ in _ORDINE}
    reasons: Dict[str, str] = {}
    found: Dict[str, object] = {}
    regole: Tuple[str, ...] = ()
    quote = claim.get("quote") or ""

    if intervento is None:
        checks["speech"] = FAIL
        i = ids.leggi_speech_id(claim.get("speech", ""))
        if i is None:
            reasons["speech"] = "unknown_speech_id_format"
        elif sedute_presenti is not None:
            sid = f"{'sen_' if i.camera == 'senato' else ''}leg{i.legislatura}_sed{i.seduta}"
            reasons["speech"] = "speech_not_in_sitting" if sid in sedute_presenti else "sitting_not_in_data"
        else:
            reasons["speech"] = "not_in_data"
    else:
        checks["speech"] = OK
        found.update(date=intervento.date, chamber=intervento.chamber, speaker=intervento.speaker_id)
        persona = fonte.persona(intervento.speaker_id) if intervento.speaker_id else None
        if persona:
            found["speaker_name"] = persona.name

        # 2-3. Testo e parole di terzi
        riscontro = trova(quote, intervento.text)
        if riscontro is None:
            checks["text"] = FAIL
            reasons["text"] = "not_in_speech_text"
        else:
            checks["text"] = OK
            regole = riscontro.regole
            terzi = parole_di_terzi(quote, intervento.text, riscontro.inizio)
            checks["own_words"] = FAIL if terzi else OK
            if terzi:
                reasons["own_words"] = terzi

        # 4. Oratore
        if not intervento.speaker_id:
            checks["speaker"], reasons["speaker"] = FAIL, "speech_has_no_speaker"
        elif ids.uri(intervento.speaker_id) == ids.uri(claim.get("speaker")):
            checks["speaker"] = OK
        else:
            checks["speaker"], reasons["speaker"] = FAIL, "different_speaker"

        # 5. Gruppo: della persona indicata, alla data dell'intervento
        apps = fonte.appartenenze(claim.get("speaker") or "") or (
            fonte.appartenenze(ids.uri(claim.get("speaker"))) if claim.get("speaker") else [])
        stato, motivo, trovato = controlla_gruppo(claim, intervento, apps)
        checks["group"], reasons["group"] = stato, motivo
        found["on_date"] = trovato

        # 6. Link
        ok, motivo = ids.controlla_link(claim.get("link") or "", intervento.speech_id,
                                        intervento.record_url, intervento.url)
        checks["link"] = OK if ok else FAIL
        if motivo != "ok":
            reasons["link"] = motivo

    esito = next((e for nome, e in _ORDINE if checks[nome] == FAIL), None)
    if esito is None:
        esito = "esatta" if not regole else "esatta_dopo_normalizzazione"
    item = {
        "index": indice,
        "speech": claim.get("speech"),
        "speaker": claim.get("speaker"),
        "group": claim.get("group"),
        "government": bool(claim.get("government")),
        "quote": quote,
        "link": claim.get("link"),
        "outcome": esito,
        "normalizations": list(regole),
        "checks": checks,
        "reasons": reasons,
        "found": found,
    }
    if claim.get("id") is not None:
        item["id"] = claim["id"]
    return item


def controlla_citazioni(risposta: dict, fonte: Fonte) -> List[dict]:
    claims = risposta.get("claims") or []
    interventi = fonte.interventi([c.get("speech") for c in claims])
    sedute = getattr(fonte, "sedute", None)
    presenti = sedute() if callable(sedute) else None
    return [controlla(n, c, interventi.get(c.get("speech")), fonte, presenti)
            for n, c in enumerate(claims, start=1)]
