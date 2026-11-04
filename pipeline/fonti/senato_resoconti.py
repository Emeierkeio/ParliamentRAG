"""Resoconti stenografici dell'Assemblea del Senato in Akoma Ntoso (XML), da senato.it.

senato.it è dietro un WAF che chiede di eseguire JavaScript: per scaricare le sedute nuove serve un browser senza
interfaccia, che la pipeline non ha ancora. Intanto questo passo importa nel lago i
resoconti già scaricati dalla pipeline precedente (`cartella_import`, file `resaula_leg19_0300.akn`): sono gli
stessi file della fonte, con la loro data e il loro indirizzo ufficiale. Alcune sedute (XIX: 212, 213, 214, 216, 218,
221, 222) il Senato le ha pubblicate solo come pagina web, senza AKN: per quelle si importa la pagina
`resaula_leg19_0212.html`, che la trasformazione legge a parte.
Chiave nel lago: `leg19-senato-sed0300`.
"""

from __future__ import annotations

import re

from ..ambiente import percorso
from ..lago import Lago

NOME = "senato_resoconti"


def scarica(ctx) -> dict:
    cfg = ctx.config["fonti"][NOME]
    leg = int(cfg["legislatura"])
    lago = Lago(ctx.cartella)
    cartella = percorso(cfg["cartella_import"]) if cfg.get("cartella_import") else None
    presenti = set(lago.chiavi(NOME))
    importati = 0
    if cartella and cartella.is_dir():
        # prima gli AKN, poi le pagine web: un HTML entra solo per le sedute senza AKN
        for f in sorted(cartella.glob(f"resaula_leg{leg}_*.akn")) + sorted(cartella.glob(f"resaula_leg{leg}_*.html")):
            numero = int(re.search(r"_(\d+)\.(?:akn|html)$", f.name).group(1))
            k = f"leg{leg}-senato-sed{numero:04d}"
            if k in presenti:
                continue
            corpo = f.read_bytes()
            if f.suffix == ".html":
                doc = re.search(rb"show-doc\?leg=\d+&amp;tipodoc=Resaula&amp;id=(\d+)", corpo)
                url = f"https://www.senato.it/show-doc?leg={leg}&tipodoc=Resaula&id={doc.group(1).decode()}&part=doc_dc" if doc else str(f)
                lago.salva(NOME, k, corpo, url, "html")
            else:
                uri = re.search(rb'<an:FRBRuri value="([^"]+)"', corpo)
                lago.salva(NOME, k, corpo, uri.group(1).decode() if uri else str(f), "akn")
            presenti.add(k)
            importati += 1
    ctx.log(f"{NOME}: {importati} resoconti importati dalla cartella; le sedute nuove aspettano il browser senza interfaccia")
    return {"importati": importati, "nel_lago": len([k for k in lago.chiavi(NOME) if "-senato-sed" in k])}
