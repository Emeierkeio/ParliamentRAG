"""Foto dei senatori della legislatura, per il sito: senato.it le serve dietro il WAF, che a un browser nuovo risponde
con la pagina di verifica, quindi il servizio le tiene nel database (tabella person_photo) e, come riserva, fra i suoi
dati (`dati/foto/senatori/{id}.jpg`, fuori dal repo). Si scaricano con il browser senza interfaccia solo quelle che
mancano, al più `massimo_richieste` per giro; quelle già sul disco e non ancora nel database si caricano senza
riscaricarle. Una foto che senato.it non ha (404) si annota in `.non_trovate.json` e si richiede di nuovo dopo 30 giorni.
"""

from __future__ import annotations

import base64
import json
import time

from ..lago import Lago
from ..carica.postgres import psql
from . import camera_ocd, senato_browser

NOME = "senato_foto"
FOTO = "https://www.senato.it/leg/{leg}/Immagini/Senatori/{id:08d}.jpg"


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg = int(cfg["legislatura"])
    cartella = ctx.cartella / "foto" / "senatori"
    cartella.mkdir(parents=True, exist_ok=True)
    u = Lago(ctx.cartella).ultimo("senato_osr", camera_ocd.chiave("persone", leg))
    if not u:
        return {"scaricate": 0, "motivo": "anagrafica del Senato non ancora nel lago"}
    ids = sorted({r["senatore"].rstrip("/").rsplit("/", 1)[-1] for r in json.loads(Lago(ctx.cartella).leggi(u["file"]))})
    f_assenti = cartella / ".non_trovate.json"
    try:
        assenti = {k: v for k, v in json.loads(f_assenti.read_text()).items() if time.time() - v < 30 * 86400}
    except (OSError, ValueError):
        assenti = {}
    mancano = [i for i in ids if i.isdigit() and not (cartella / f"{int(i)}.jpg").is_file() and i not in assenti]
    fatte = 0
    if mancano:
        try:
            with senato_browser.Sessione(pausa=float(cfg.get("pausa_secondi", 2)), massimo=int(cfg.get("massimo_richieste", 50)), ctx=ctx) as s:
                for i in mancano:
                    try:
                        corpo = s.scarica(FOTO.format(leg=leg, id=int(i)))
                    except senato_browser.NonTrovato:
                        assenti[i] = time.time()
                        continue
                    if corpo[:3] == b"\xff\xd8\xff":                 # solo JPEG veri: non la pagina di verifica
                        (cartella / f"{int(i)}.jpg").write_bytes(corpo)
                        fatte += 1
        except senato_browser.Bloccato as e:
            ctx.log(f"{NOME}: {e}")
        finally:
            f_assenti.write_text(json.dumps(assenti))
    nel_db = {r.strip() for r in psql("\\t on\n\\a\nSELECT person FROM person_photo WHERE person LIKE 'it:person:senato:%';\n").splitlines() if r.strip()}
    nuove = [f for f in sorted(cartella.glob("*.jpg")) if f"it:person:senato:{f.stem}" not in nel_db]
    for i in range(0, len(nuove), 50):
        righe = ",\n".join(f"('it:person:senato:{f.stem}', decode('{base64.b64encode(f.read_bytes()).decode()}', 'base64'), "
                           f"'{FOTO.format(leg=leg, id=int(f.stem))}')" for f in nuove[i:i + 50])
        psql(f"INSERT INTO person_photo (person, image, source_url) VALUES\n{righe}\nON CONFLICT (person) DO UPDATE SET "
             "image = EXCLUDED.image, source_url = EXCLUDED.source_url, updated = now();\n")
    return {"scaricate": fatte, "mancano": len(mancano) - fatte, "non_trovate": len(assenti), "nel_database": len(nuove)}
