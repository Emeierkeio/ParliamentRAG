"""Identificatori: interventi, persone, gruppi e link ai resoconti.

- Interventi: lo `speech_id` del dataset. Camera `leg19_sed15_tit00070.sub00020.int00020`,
  Senato `sen_leg19_sed321_p16725_deb0_5`. Mai l'ID di un chunk: il dataset
  pubblico non li contiene.
- Persone: l'URI ufficiale (`http://dati.camera.it/ocd/persona.rdf/p308798`,
  `http://dati.senato.it/senatore/1103`); per i membri del Governo senza seggio
  l'ID del dataset (`gov_abodi_andrea`).
- Gruppi: l'URI ufficiale (`http://dati.camera.it/ocd/gruppoParlamentare.rdf/gr4133`,
  `http://dati.senato.it/gruppo/85`); per le componenti del Misto l'URI della
  componente come lo dà il dataset.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_SPEECH = re.compile(r"^(?P<senato>sen_)?leg(?P<leg>\d+)_sed(?P<sed>\d+)_(?P<resto>.+)$")
_CHUNK = re.compile(r"_chunk_\d+$")


@dataclass(frozen=True)
class IdIntervento:
    camera: str          # "camera" | "senato"
    legislatura: int
    seduta: int
    resto: str


def leggi_speech_id(speech_id: str) -> Optional[IdIntervento]:
    m = _SPEECH.match(speech_id or "")
    if not m:
        return None
    return IdIntervento("senato" if m.group("senato") else "camera", int(m.group("leg")),
                        int(m.group("sed")), m.group("resto"))


def da_chunk(chunk_id: str) -> str:
    """L'intervento di un chunk: l'ID del chunk è quello dell'intervento più `_chunk_N`."""
    return _CHUNK.sub("", chunk_id or "")


def uri(valore: Optional[str]) -> str:
    """Forma canonica per confrontare due URI: http, senza barra finale."""
    v = (valore or "").strip()
    if v.startswith("https://dati."):
        v = "http://" + v[len("https://"):]
    return v.rstrip("/")


# ---------------------------------------------------------------------------
# Link al resoconto
# ---------------------------------------------------------------------------

def link_camera(speech_id: str) -> Optional[str]:
    """Il link al resoconto stenografico della Camera, aperto sull'intervento."""
    i = leggi_speech_id(speech_id)
    if not i or i.camera != "camera":
        return None
    sed = f"{i.seduta:04d}"
    return (f"https://www.camera.it/leg{i.legislatura}/410?idSeduta={sed}&tipo=stenografico"
            f"#sed{sed}.stenografico.{i.resto}")


def controlla_link(link: str, speech_id: str, resoconto_seduta: Optional[str] = None,
                   pagina_intervento: Optional[str] = None) -> Tuple[bool, str]:
    """Il link porta al resoconto della seduta dell'intervento? Senza scaricarlo.

    Camera: www.camera.it/leg{L}/410 con idSeduta uguale alla seduta e
    tipo=stenografico; se c'è l'ancora, deve indicare la seduta e un tratto
    dell'intervento (titolo, sottotitolo o intervento stesso).
    Senato: la pagina dell'intervento o il resoconto della seduta su
    www.senato.it (show-doc, tipodoc=Resaula, leg giusta). L'id del documento
    si confronta quando il dataset dà il resoconto della seduta.

    Restituisce (esito, motivo).
    """
    i = leggi_speech_id(speech_id)
    if i is None:
        return False, "unknown_speech_id_format"
    try:
        u = urllib.parse.urlsplit((link or "").strip())
    except ValueError:
        return False, "not_a_url"
    if u.scheme not in ("http", "https"):
        return False, "not_a_url"
    host = u.netloc.lower()
    query = urllib.parse.parse_qs(u.query)

    if i.camera == "camera":
        if host not in ("www.camera.it", "camera.it"):
            return False, "wrong_site"
        if u.path.rstrip("/") != f"/leg{i.legislatura}/410":
            return False, "wrong_page"
        sed = (query.get("idSeduta") or [""])[0]
        if not sed.isdigit() or int(sed) != i.seduta:
            return False, "wrong_sitting"
        if (query.get("tipo") or [""])[0] != "stenografico":
            return False, "not_the_record"
        if u.fragment:
            m = re.match(r"^sed(\d+)\.stenografico(?:\.(.+))?$", u.fragment)
            if not m or int(m.group(1)) != i.seduta:
                return False, "wrong_anchor"
            if m.group(2) and not _prefisso_di(m.group(2), i.resto):
                return False, "wrong_anchor"
        return True, "ok"

    if host not in ("www.senato.it", "senato.it"):
        return False, "wrong_site"
    for atteso in (pagina_intervento, resoconto_seduta):
        if atteso and _stesso_documento(link, atteso):
            return True, "ok"
    if u.path.rstrip("/") != "/show-doc":
        return False, "wrong_page"
    if (query.get("leg") or [""])[0] != str(i.legislatura):
        return False, "wrong_legislature"
    if (query.get("tipodoc") or [""])[0] != "Resaula":
        return False, "not_the_record"
    if resoconto_seduta:
        return False, "wrong_sitting"
    return True, "ok_format_only"


def _prefisso_di(ancora: str, resto: str) -> bool:
    """`tit00070.sub00020` indica un tratto di `tit00070.sub00020.int00020`."""
    pezzi, tutti = ancora.split("."), resto.split(".")
    return pezzi == tutti[:len(pezzi)]


def _stesso_documento(a: str, b: str) -> bool:
    ua, ub = urllib.parse.urlsplit(a), urllib.parse.urlsplit(b)
    qa, qb = urllib.parse.parse_qs(ua.query), urllib.parse.parse_qs(ub.query)
    return (ua.netloc.lower().removeprefix("www.") == ub.netloc.lower().removeprefix("www.")
            and ua.path.rstrip("/") == ub.path.rstrip("/")
            and all(qa.get(k) == qb.get(k) for k in ("leg", "tipodoc", "id")))


# ---------------------------------------------------------------------------
# Gruppi: dal nome nel dataset all'URI ufficiale
# ---------------------------------------------------------------------------

_SIGLA_FINALE = re.compile(r"\s*\((?:[^()\s]|\([^()\s]*\))+\)$")
_APOSTROFI = re.compile(r"[’‘ʼ`´]")


def chiave_nome(nome: str) -> str:
    """Il nome di un gruppo in una forma confrontabile.

    Maiuscole, apostrofi dritti, trattini senza spazi intorno, senza la sigla
    finale tra parentesi: «Italia Viva - Casa Riformista» e
    «ITALIA VIVA-CASA RIFORMISTA (IV-CR)» hanno la stessa chiave.
    """
    n = _APOSTROFI.sub("'", (nome or "").upper())
    n = re.sub(r"\s*-\s*", "-", " ".join(n.split()))
    return _SIGLA_FINALE.sub("", n).strip()


@lru_cache(maxsize=1)
def tabella_gruppi() -> Dict[str, List[dict]]:
    """chiave del nome -> gruppi ufficiali con quel nome (uno per camera)."""
    dati = json.loads(Path(__file__).with_name("gruppi_ufficiali.json").read_text())
    out: Dict[str, List[dict]] = {}
    for g in dati["groups"]:
        for n in g["names"]:
            out.setdefault(chiave_nome(n["name"]), []).append(g)
    return out


def uri_gruppo(nome: str, camera: Optional[str] = None) -> Optional[str]:
    """L'URI ufficiale di un gruppo dal suo nome (una qualsiasi delle sue denominazioni)."""
    trovati = tabella_gruppi().get(chiave_nome(nome), [])
    if camera:
        stessa = [g for g in trovati if g["chamber"] == camera]
        if stessa:
            return stessa[0]["uri"]
    # Senza camera: i nomi esatti di Camera (maiuscolo) e Senato si distinguono
    esatti = [g for g in trovati if any(n["name"] == nome for n in g["names"])]
    if len(esatti) == 1:
        return esatti[0]["uri"]
    return trovati[0]["uri"] if len(trovati) == 1 else None


def camera_della_persona(persona: str) -> Optional[str]:
    """camera per i deputati, senato per i senatori, None per gli ID del dataset (gov_…)."""
    u = uri(persona)
    if u.startswith("http://dati.camera.it/"):
        return "camera"
    if u.startswith("http://dati.senato.it/"):
        return "senato"
    return None


@lru_cache(maxsize=1)
def _misti() -> frozenset:
    dati = json.loads(Path(__file__).with_name("gruppi_ufficiali.json").read_text())
    return frozenset(uri(g["uri"]) for g in dati["groups"]
                     if any(chiave_nome(n["name"]) == "MISTO" for n in g["names"]))


def e_il_misto(uri_ufficiale: str) -> bool:
    """L'URI è quello del gruppo Misto (di una delle due camere)?"""
    return uri(uri_ufficiale) in _misti()
