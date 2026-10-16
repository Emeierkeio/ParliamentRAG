"""Le fonti dei dati: il dataset pubblico su Hugging Face, in locale.

Il controllo delle citazioni chiede a una fonte tre cose: un intervento con
testo, oratore, data e seduta; le appartenenze di una persona (gruppi,
componenti del Misto, incarichi di governo) con le date; la versione dei
dati. `DatiHF` le legge dai parquet di `emeierkeio/parliamentrag-leg19`.
Chi ha i dati altrove (per esempio il grafo da cui il dataset è esportato)
scrive un'altra classe con gli stessi tre metodi e ottiene lo stesso controllo.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol

DATASET = "emeierkeio/parliamentrag-leg19"
FILE_NECESSARI = ("speeches.parquet", "sessions.parquet", "memberships.parquet",
                  "organizations.parquet", "persons.parquet", "export_meta.json")
HF = "https://huggingface.co"


@dataclass(frozen=True)
class Intervento:
    speech_id: str
    chamber: str
    date: Optional[str]
    session_id: Optional[str]
    speaker_id: Optional[str]
    text: str
    # Pagina ufficiale dell'intervento e resoconto della seduta, se la fonte li dà
    url: Optional[str] = None
    record_url: Optional[str] = None


@dataclass(frozen=True)
class Appartenenza:
    org_type: str                 # group | misto_component | government | committee
    name: str
    start: Optional[str]
    end: Optional[str]
    chamber: Optional[str] = None
    uri: Optional[str] = None
    role: Optional[str] = None

    def valida_il(self, data: str) -> bool:
        return bool(self.start) and self.start <= data and (not self.end or self.end >= data)


@dataclass(frozen=True)
class Persona:
    person_id: str
    name: str


class Fonte(Protocol):
    def interventi(self, ids: Iterable[str]) -> Dict[str, Intervento]: ...
    def appartenenze(self, person_id: str) -> List[Appartenenza]: ...
    def persona(self, person_id: str) -> Optional[Persona]: ...
    def versione(self) -> dict: ...


def _str(v) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, float) and v != v:  # NaN
        return None
    s = str(v).strip()
    return s or None


class DatiHF:
    """Il dataset Hugging Face in una cartella locale (vedi `scarica`)."""

    def __init__(self, cartella):
        self.cartella = Path(cartella)
        mancano = [f for f in FILE_NECESSARI if not (self.cartella / f).exists()]
        if mancano:
            raise FileNotFoundError(f"Nella cartella {self.cartella} mancano: {', '.join(mancano)}")
        self._meta = json.loads((self.cartella / "export_meta.json").read_text())
        v = self.cartella / "versione.json"
        self._origine = json.loads(v.read_text()) if v.exists() else {}
        self._cache: Dict[str, Optional[Intervento]] = {}
        self._appartenenze: Optional[Dict[str, List[Appartenenza]]] = None
        self._persone: Optional[Dict[str, Persona]] = None
        self._sedute: Optional[Dict[str, dict]] = None

    # -- tabelle piccole, lette una volta --------------------------------

    def _tabella(self, nome: str, colonne: Optional[List[str]] = None, filtri=None) -> List[dict]:
        import pyarrow.parquet as pq
        path = self.cartella / f"{nome}.parquet"
        presenti = set(pq.read_schema(path).names)
        cols = [c for c in colonne if c in presenti] if colonne else None
        return pq.read_table(path, columns=cols, filters=filtri).to_pylist()

    def _carica_sedute(self) -> Dict[str, dict]:
        if self._sedute is None:
            self._sedute = {r["session_id"]: r for r in
                            self._tabella("sessions", ["session_id", "chamber", "date", "record_url"])}
        return self._sedute

    def _carica_appartenenze(self) -> Dict[str, List[Appartenenza]]:
        if self._appartenenze is None:
            uri_org: Dict[tuple, str] = {}
            for o in self._tabella("organizations", ["org_type", "chamber", "name", "uri"]):
                if _str(o.get("uri")):
                    uri_org[(o["org_type"], o["name"], _str(o.get("chamber")))] = o["uri"]
                    uri_org.setdefault((o["org_type"], o["name"], None), o["uri"])
            out: Dict[str, List[Appartenenza]] = {}
            for m in self._tabella("memberships", ["person_id", "org_type", "chamber", "org_name",
                                                   "role", "start_date", "end_date"]):
                camera = _str(m.get("chamber"))
                chiave = (m["org_type"], m["org_name"])
                out.setdefault(m["person_id"], []).append(Appartenenza(
                    org_type=m["org_type"], name=m["org_name"], start=_str(m.get("start_date")),
                    end=_str(m.get("end_date")), chamber=camera,
                    uri=uri_org.get(chiave + (camera,)) or uri_org.get(chiave + (None,)),
                    role=_str(m.get("role"))))
            self._appartenenze = out
        return self._appartenenze

    # -- interfaccia Fonte -----------------------------------------------

    def interventi(self, ids: Iterable[str]) -> Dict[str, Intervento]:
        da_leggere = sorted({i for i in ids if i and i not in self._cache})
        if da_leggere:
            righe = self._tabella("speeches", ["speech_id", "chamber", "session_id", "date",
                                               "speaker_id", "text", "url"],
                                  filtri=[("speech_id", "in", da_leggere)])
            sedute = self._carica_sedute()
            for r in righe:
                seduta = sedute.get(r.get("session_id")) or {}
                camera = _str(r.get("chamber")) or _str(seduta.get("chamber")) or (
                    "senato" if r["speech_id"].startswith("sen_") else "camera")
                self._cache[r["speech_id"]] = Intervento(
                    speech_id=r["speech_id"], chamber=camera, date=_str(r.get("date")),
                    session_id=_str(r.get("session_id")), speaker_id=_str(r.get("speaker_id")),
                    text=r.get("text") or "", url=_str(r.get("url")),
                    record_url=_str(seduta.get("record_url")))
            for i in da_leggere:
                self._cache.setdefault(i, None)
        return {i: self._cache[i] for i in ids if self._cache.get(i)}

    def appartenenze(self, person_id: str) -> List[Appartenenza]:
        return self._carica_appartenenze().get(person_id, [])

    def sedute(self) -> set:
        """Le sedute presenti in questa versione: dice se un intervento manca o manca la seduta."""
        return set(self._carica_sedute())

    def persona(self, person_id: str) -> Optional[Persona]:
        if self._persone is None:
            self._persone = {}
            for p in self._tabella("persons", ["person_id", "first_name", "last_name"]):
                nome = " ".join(x for x in (_str(p.get("first_name")), _str(p.get("last_name"))) if x)
                self._persone[p["person_id"]] = Persona(p["person_id"], nome.title())
        return self._persone.get(person_id)

    def versione(self) -> dict:
        sedute = self._carica_sedute().values()
        fino_a: Dict[str, str] = {}
        for s in sedute:
            camera = _str(s.get("chamber")) or ("senato" if s["session_id"].startswith("sen_") else "camera")
            if s.get("date") and s["date"] > fino_a.get(camera, ""):
                fino_a[camera] = s["date"]
        generato = self._meta.get("generated_at") or ""
        return {
            "source": "huggingface",
            "dataset": self._origine.get("dataset", DATASET),
            "version": generato[:10] or None,
            "revision": self._origine.get("commit") or self._origine.get("revision"),
            "generated_at": generato or None,
            "chambers": sorted(fino_a),
            "through": dict(sorted(fino_a.items())),
        }


# ---------------------------------------------------------------------------
# Scaricamento
# ---------------------------------------------------------------------------

def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "parliamentrag-verifica"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def commit_di(revisione: str, dataset: str = DATASET) -> Optional[str]:
    """Il commit del dataset per una revisione (tag, ramo o commit); None se non esiste."""
    try:
        info = json.loads(_get(f"{HF}/api/datasets/{dataset}/revision/{revisione}"))
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            return None
        raise
    return info.get("sha")


def scarica(cartella, revisione: str = "main", dataset: str = DATASET, avvisa=print) -> Path:
    """Scarica nella cartella i file del dataset che servono alla verifica.

    `revisione` è un tag, un ramo o un commit del dataset su Hugging Face. I
    file si prendono dal commit risolto, così la cartella corrisponde a una
    sola versione anche se il ramo nel frattempo si sposta.
    """
    cartella = Path(cartella)
    commit = commit_di(revisione, dataset)
    if commit is None:
        raise ValueError(f"La versione {revisione!r} del dataset {dataset} non esiste su Hugging Face")
    cartella.mkdir(parents=True, exist_ok=True)
    for nome in FILE_NECESSARI:
        avvisa(f"scarico {nome} ({dataset}@{commit[:8]})")
        dati = _get(f"{HF}/datasets/{dataset}/resolve/{commit}/{nome}", timeout=600)
        (cartella / (nome + ".parziale")).write_bytes(dati)
        (cartella / (nome + ".parziale")).replace(cartella / nome)
    (cartella / "versione.json").write_text(json.dumps(
        {"dataset": dataset, "revision": revisione, "commit": commit}, indent=1) + "\n")
    return cartella
