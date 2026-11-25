"""Le leggi come le chiamano giornali e cittadini: «premierato», «separazione delle carriere», «legge di bilancio 2026».
Il titolo ufficiale non ha quelle parole («Norme in materia di ordinamento giurisdizionale e di istituzione della Corte
disciplinare»), quindi la ricerca per parole porta altrove. Ogni soprannome è legato agli atti veri, controllati sul
database il 25/11/2026 (tests/test_atti_ricerca.py verifica che esistano). Un soprannome nuovo si aggiunge qui, con gli
atti di tutti e due i rami e delle letture successive."""

from __future__ import annotations

import re

# (espressione sul testo cercato, in minuscolo; atti)
SOPRANNOMI: list[tuple[str, list[str]]] = [
    # ddl costituzionale Casellati sull'elezione diretta del Presidente del Consiglio
    (r"premierato|elezione diretta del premier", ["it:senato:19:ddl:935", "it:camera:19:ac:1921"]),
    # ddl costituzionale Nordio: ordinamento giurisdizionale e Corte disciplinare, con le seconde letture
    (r"separazione delle carriere|riforma (nordio )?della giustizia|riforma nordio|ddl nordio",
     ["it:camera:19:ac:1917", "it:senato:19:ddl:1353", "it:camera:19:ac:1917-B", "it:senato:19:ddl:1353-B"]),
    # ddl Nordio su abuso d'ufficio e traffico di influenze (legge 114/2024)
    (r"abuso d.ufficio|ddl nordio", ["it:senato:19:ddl:808", "it:camera:19:ac:1718"]),
    # ddl Calderoli (legge 86/2024)
    (r"autonomia differenziata|ddl calderoli", ["it:senato:19:ddl:615", "it:camera:19:ac:1665"]),
    # ddl sicurezza (C. 1660, S. 1236) e decreti-legge sulla sicurezza pubblica: 48/2025, 23/2026, 190/2026
    (r"(ddl|decret\w*|pacchetto) sicurezza",
     ["it:camera:19:ac:1660", "it:senato:19:ddl:1236", "it:camera:19:ac:2355", "it:senato:19:ddl:1509",
      "it:senato:19:ddl:1818", "it:camera:19:ac:2886", "it:camera:19:ac:3159"]),
    # decreto-legge 123/2023 sul disagio giovanile
    (r"decreto caivano", ["it:senato:19:ddl:878", "it:camera:19:ac:1517"]),
    # decreto-legge 20/2023 sui flussi di ingresso
    (r"decreto cutro", ["it:senato:19:ddl:591", "it:camera:19:ac:1112"]),
    # ratifica del protocollo con l'Albania sui centri per i migranti (legge 14/2024)
    (r"protocollo (italia.)?albania|accordo (italia.)?albania|centri in albania", ["it:camera:19:ac:1620", "it:senato:19:ddl:995"]),
    # decreti-legge «termini normativi» di fine anno: 198/2022, 215/2023, 202/2024, 200/2025
    (r"milleproroghe",
     ["it:senato:19:ddl:452", "it:camera:19:ac:888", "it:camera:19:ac:1633", "it:senato:19:ddl:1027",
      "it:senato:19:ddl:1337", "it:camera:19:ac:2245", "it:senato:19:ddl:1812", "it:camera:19:ac:2753"]),
]

# «legge di bilancio 2026», «manovra 2026», «finanziaria 2026»: il bilancio di previsione per quell'anno finanziario
BILANCIO = re.compile(r"(?:legge di bilancio|manovra(?: finanziaria)?|legge finanziaria|finanziaria)(?: per il| del)? (20\d\d)")


def cerca(q: str | None) -> tuple[list[str] | None, str | None]:
    """Gli atti di un soprannome contenuto in `q` (None se nessuno) e, per la legge di bilancio di un anno, l'espressione
    regolare (Postgres e Python) che ne riconosce il titolo, alla Camera preceduto da «S. 1689. - »."""
    if not q:
        return None, None
    s = q.lower()
    uris = list(dict.fromkeys(u for rx, us in SOPRANNOMI if re.search(rx, s) for u in us))
    m = BILANCIO.search(s)
    titolo = rf'^(S\. [0-9]+\. *[-–] *)?"?Bilancio di previsione dello Stato per l.anno finanziario {m[1]}' if m else None
    return uris or None, titolo
