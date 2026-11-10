"""Atti del Governo e proposte di nomina sottoposti al parere parlamentare, alla Camera: schemi di decreto legislativo,
regolamenti, decreti ministeriali e nomine negli enti pubblici. Non sono progetti di legge: passano solo dalle
commissioni, che danno un parere entro un termine.

Una pagina sola elenca tutti gli atti della legislatura (circa 600), ognuno con la fase, le commissioni a cui è
assegnato, la data, il termine e il parere espresso: una richiesta per notte. Chiave nel lago:
`leg19-atti-governo`; le versioni precedenti restano nel lago.
"""

from __future__ import annotations

from ..lago import Lago, controlla_calo
from .camera_bollettino import _get

NOME = "camera_atti_governo"
PAGINA = "https://www.camera.it/leg{leg}/142"


def conta(pagina: bytes) -> int:
    return pagina.count(b'<li tipo="atto"') + pagina.count(b'<li tipo="nomina"')


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg = int(cfg["legislatura"])
    u = PAGINA.format(leg=leg)
    corpo = _get(u)
    quanti = conta(corpo) if corpo else 0
    if not quanti:
        raise RuntimeError("pagina degli atti del Governo vuota o cambiata: nessun atto nell'elenco")
    lago = Lago(ctx.cartella)
    # l'elenco cresce soltanto: una pagina con meno atti di ieri è arrivata a metà
    controlla_calo(lago, NOME, f"leg{leg}-atti-governo", quanti, conta=conta, massimo=float(cfg.get("calo_massimo", 0.05)))
    r = lago.salva(NOME, f"leg{leg}-atti-governo", corpo, u, "htm")
    ctx.log(f"{NOME}: {quanti} atti e nomine, {'nuovo' if r.get('nuovo') else 'invariato'}")
    return {"atti": quanti, "nuovo": bool(r.get("nuovo"))}
