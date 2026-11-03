"""Documenti del Senato in Akoma Ntoso dai bulk data ufficiali su GitHub (SenatoDellaRepubblica/AkomaNtosoBulkData,
CC BY 4.0, aggiornati ogni giorno dal Servizio dell'Informatica del Senato). Su GitHub non c'è il WAF di senato.it:
niente browser e niente limite di richieste.

Il repository è ordinato per atto (`Leg19/Atto00058173/resaula/01413815-ra.akn.xml`) e pesa 1,7 GB con tutte le
legislature: se ne tiene un clone parziale (`--filter=blob:none`, profondità 1) con solo le cartelle che servono
(`sparse-checkout`); git scarica in blocco solo i file nuovi o cambiati.

Nel lago:
- resoconti stenografici dell'Assemblea (`resaula`): uno per seduta, `leg19-senato-sed0465`, la stessa chiave dei
  resoconti importati dalla cartella (`senato_resoconti`), che restano se ci sono già;
- resoconti sommari delle commissioni (`sommcomm`): uno per seduta, `leg19-senato-som-7acommissionepermanente-sed0344`;
- testi dei ddl (`ddlpres` presentato, `ddlcomm` della commissione, `ddlmess` messaggio): uno per testo,
  `leg19-senato-testo-ddlcomm-01496679`;
- emendamenti d'Aula (`emend`) e di commissione (`emendc`): uno per ddl e sede, `leg19-senato-eme-1110-A`, un JSON
  compresso con tutti i file di quel ddl (lo stesso emendamento compare sotto più fasi dell'atto: si tiene una volta).
"""

from __future__ import annotations

import gzip
import json
import re
import subprocess
from pathlib import Path

from ..lago import Lago
from ..trasforma.senato_sommario import codice_organo

NOME = "senato_akn"
REPO = "https://github.com/SenatoDellaRepubblica/AkomaNtosoBulkData.git"
RESOCONTI = "senato_resoconti"           # stessa fonte dei resoconti importati: una sola chiave per seduta


def _git(cartella: Path, *argomenti: str, timeout: int = 3600) -> str:
    r = subprocess.run(["git", "-C", str(cartella), *argomenti], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(argomenti[:2])}: {r.stderr[-400:]}")
    return r.stdout


def aggiorna_clone(cartella: Path, leg: int, tipi: list[str]) -> str:
    """Clone parziale aggiornato all'ultima versione, con solo le cartelle `tipi` della legislatura. Restituisce il commit."""
    if not (cartella / ".git").exists():
        cartella.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", "--depth", "1", REPO, str(cartella)],
                           capture_output=True, text=True, timeout=3600)
        if r.returncode:
            raise RuntimeError(f"git clone: {r.stderr[-400:]}")
    else:
        _git(cartella, "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", "master")
    _git(cartella, "sparse-checkout", "set", "--no-cone", *[f"/Leg{leg}/*/{t}/*" for t in tipi])
    _git(cartella, "checkout", "-q", "-B", "master", "FETCH_HEAD" if (cartella / ".git" / "FETCH_HEAD").exists() else "origin/master")
    return _git(cartella, "rev-parse", "HEAD").strip()


def _numero_seduta(corpo: bytes) -> int | None:
    m = re.search(rb'<an:FRBRnumber value="(\d+)"', corpo)
    return int(m.group(1)) if m else None


def _ddl_e_sede(corpo: bytes) -> tuple[str, str] | None:
    """Da «http://dati.senato.it/19/Emend/S/1101 NT/C/4.1» a («1101 NT», «C»)."""
    m = re.search(rb'<an:FRBRuri value="http://dati\.senato\.it/\d+/Emend/S/([^/"]+)/([A-Z]+)/', corpo)
    return (m.group(1).decode().strip(), m.group(2).decode()) if m else None


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg, tipi = int(cfg["legislatura"]), list(cfg.get("tipi", ["resaula", "emend", "emendc"]))
    cartella = (ctx.cartella / cfg.get("cartella_clone", "cache/senato_akn")).resolve()
    commit = aggiorna_clone(cartella, leg, tipi)
    lago = Lago(ctx.cartella)
    radice = cartella / f"Leg{leg}"
    esito = {"commit": commit[:12]}

    if "resaula" in tipi:
        presenti, nuove = set(lago.chiavi(RESOCONTI)), 0
        sedute: dict[int, Path] = {}
        for f in sorted(radice.glob("*/resaula/*-ra.akn.xml")):
            n = _numero_seduta(f.read_bytes()[:20000])
            if n and n not in sedute:
                sedute[n] = f
        for n, f in sorted(sedute.items()):
            k = f"leg{leg}-senato-sed{n:04d}"
            if k not in presenti:
                lago.salva(RESOCONTI, k, f.read_bytes(), f"{REPO}#{f.relative_to(cartella)}", "akn")
                nuove += 1
        esito["resoconti"] = {"sedute": len(sedute), "nuove": nuove}

    if "sommcomm" in tipi:
        visti, nuovi = set(), 0
        for f in sorted(radice.glob("*/sommcomm/*-rc.akn.xml")):
            corpo = f.read_bytes()
            m = re.search(rb'<an:FRBRuri value="[^"]*/SOMMCOMM/([^/"]+)/\d{4}-\d{2}-\d{2}/(\d+)"', corpo)
            if not m:
                continue
            k = f"leg{leg}-senato-som-{codice_organo(m.group(1).decode())}-sed{int(m.group(2)):04d}"
            if k in visti:                                      # la stessa seduta sotto più atti: una volta
                continue
            visti.add(k)
            if lago.salva(NOME, k, corpo, f"{REPO}#{f.relative_to(cartella)}", "akn")["nuovo"]:
                nuovi += 1
        esito["sommari_commissioni"] = {"sedute": len(visti), "nuovi_o_cambiati": nuovi}

    testi = [t for t in ("ddlpres", "ddlcomm", "ddlmess") if t in tipi]
    if testi:
        visti, nuovi = set(), 0
        for t in testi:
            for f in sorted(radice.glob(f"*/{t}/*-ft.akn.xml")):
                k = f"leg{leg}-senato-testo-{t}-{f.name.split('-')[0]}"
                if k in visti:
                    continue
                visti.add(k)
                if lago.salva(NOME, k, f.read_bytes(), f"{REPO}#{f.relative_to(cartella)}", "akn")["nuovo"]:
                    nuovi += 1
        esito["testi_ddl"] = {"testi": len(visti), "nuovi_o_cambiati": nuovi}

    gruppi: dict[tuple[str, str], dict[str, str]] = {}
    for t in ("emend", "emendc"):
        if t not in tipi:
            continue
        for f in sorted(radice.glob(f"*/{t}/*-em.akn.xml")):
            corpo = f.read_bytes()
            ds = _ddl_e_sede(corpo)
            if ds:
                gruppi.setdefault(ds, {}).setdefault(f.name, corpo.decode("utf-8", errors="replace"))
    cambiati = 0
    for (ddl, sede), files in sorted(gruppi.items()):
        corpo = gzip.compress(json.dumps(files, ensure_ascii=False, sort_keys=True).encode(), mtime=0)
        if lago.salva(NOME, f"leg{leg}-senato-eme-{ddl.replace(' ', '_')}-{sede}", corpo, REPO, "json.gz")["nuovo"]:
            cambiati += 1
    if gruppi:
        esito["emendamenti"] = {"gruppi": len(gruppi), "file": sum(len(v) for v in gruppi.values()), "nuovi_o_cambiati": cambiati}
    ctx.log(f"{NOME}: {json.dumps(esito, ensure_ascii=False)}")
    return esito
