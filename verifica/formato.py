"""Il formato della risposta verificabile, versione 1.

Lo schema completo è in schema/verifiable-answer.v1.json. Qui c'è lo stesso
controllo scritto a mano, senza dipendenze, con messaggi in italiano per chi
usa la riga di comando o la pagina /verifica. I test controllano che i due
dicano la stessa cosa.
"""
from __future__ import annotations

import re
from typing import List

SCHEMA_V1 = "https://w3id.org/parliamentrag/verify/v1"

_SPEECH = re.compile(r"^(sen_)?leg[0-9]+_sed[0-9]+_.+$")
_PERSONA = re.compile(r"^(https?://dati\.camera\.it/ocd/persona\.rdf/p[0-9]+|https?://dati\.senato\.it/senatore/[0-9]+|gov_[a-z0-9_]+)$")
_GRUPPO = re.compile(r"^(https?://dati\.camera\.it/ocd/(gruppoParlamentare\.rdf/gr|componenteGruppoMisto\.rdf/cgm)[0-9]+"
                     r"|https?://dati\.senato\.it/gruppo/[0-9]+"
                     r"|https://www\.senato\.it/composizione/gruppi-parlamentari/.+#.+)$")
_CAMPI = {"schema", "system", "question", "generated_at", "period", "chambers", "data_version",
          "declared_absent", "claims", "text"}
_CAMPI_CLAIM = {"id", "speaker", "group", "government", "speech", "quote", "link"}


class FormatoNonValido(ValueError):
    def __init__(self, errori: List[str]):
        super().__init__("; ".join(errori))
        self.errori = errori


def errori(risposta) -> List[str]:
    """Gli errori di formato, in italiano. Lista vuota se la risposta è valida."""
    if not isinstance(risposta, dict):
        return ["la risposta deve essere un oggetto JSON"]
    out = []
    if risposta.get("schema") != SCHEMA_V1:
        out.append(f"il campo schema deve valere {SCHEMA_V1}")
    for k in sorted(set(risposta) - _CAMPI):
        out.append(f"campo sconosciuto: {k}")
    system = risposta.get("system")
    if not isinstance(system, dict) or not isinstance(system.get("name"), str) or not system["name"]:
        out.append("manca system.name, il nome del sistema che ha scritto la risposta")
    if not isinstance(risposta.get("question"), str) or not risposta["question"]:
        out.append("manca question, la domanda")
    if not isinstance(risposta.get("data_version"), str) or not risposta["data_version"]:
        out.append("manca data_version, la versione dei dati usata")
    camere = risposta.get("chambers")
    if camere is not None and (not isinstance(camere, list) or any(c not in ("camera", "senato") for c in camere)):
        out.append("chambers può contenere solo camera e senato")
    for n, a in enumerate(risposta.get("declared_absent") or [], start=1):
        if not isinstance(a, dict) or not _GRUPPO.match(str(a.get("group", ""))) \
                or a.get("reason") not in ("no_speeches", "no_members", "other"):
            out.append(f"gruppo assente {n}: servono group (URI ufficiale) e reason (no_speeches, no_members, other)")
    claims = risposta.get("claims")
    if not isinstance(claims, list):
        out.append("manca claims, l'elenco delle citazioni")
        return out
    for n, c in enumerate(claims, start=1):
        dove = f"citazione {n}"
        if not isinstance(c, dict):
            out.append(f"{dove}: deve essere un oggetto")
            continue
        for k in sorted(set(c) - _CAMPI_CLAIM):
            out.append(f"{dove}: campo sconosciuto {k}")
        for k in ("speaker", "speech", "quote", "link"):
            if not isinstance(c.get(k), str) or not c[k]:
                out.append(f"{dove}: manca {k}")
        if isinstance(c.get("speech"), str) and c["speech"] and not _SPEECH.match(c["speech"]):
            out.append(f"{dove}: speech deve essere lo speech_id del dataset (per esempio leg19_sed15_tit00070.sub00020.int00020), non {c['speech']!r}")
        if isinstance(c.get("speaker"), str) and c["speaker"] and not _PERSONA.match(c["speaker"]):
            out.append(f"{dove}: speaker deve essere l'URI ufficiale della persona, non {c['speaker']!r}")
        governo = c.get("government")
        if governo is not None and not isinstance(governo, bool):
            out.append(f"{dove}: government deve essere true o false")
        if governo is True:
            if "group" in c:
                out.append(f"{dove}: con government true il gruppo non va indicato")
        elif not isinstance(c.get("group"), str) or not c["group"]:
            out.append(f"{dove}: manca group (oppure government: true)")
        elif not _GRUPPO.match(c["group"]):
            out.append(f"{dove}: group deve essere l'URI ufficiale del gruppo o della componente del Misto, non {c['group']!r}")
        if isinstance(c.get("link"), str) and c["link"] and not re.match(r"^https?://", c["link"]):
            out.append(f"{dove}: link deve essere un indirizzo web")
    return out


def valida(risposta) -> dict:
    e = errori(risposta)
    if e:
        raise FormatoNonValido(e)
    return risposta
