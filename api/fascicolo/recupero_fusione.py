"""Fusione dei due canali in un insieme vario e bilanciato fra i partiti, come nel backend precedente.

Il punteggio è una somma pesata di pertinenza (similarità), varietà di chi parla, copertura dei partiti, autorevolezza
e rilievo politico del brano; la scelta poi limita i brani per persona e per partito e porta ogni partito atteso
almeno a MINIMO_PER_PARTITO, togliendo i brani peggiori dei partiti che ne hanno di più. L'autorevolezza qui è
costante (0,5): si calcola dopo il recupero. Il rilievo politico (citabilità) nel v3 non c'è: vale 0,5 per tutti."""

from __future__ import annotations

from collections import defaultdict

PESI = {"pertinenza": 0.35, "varieta": 0.15, "copertura": 0.20, "autorevolezza": 0.05, "rilievo": 0.25}
MINIMO_PER_PARTITO = 5
NEUTRO = 0.5
SOGLIA_OLTRE_TETTO = 0.8          # un partito oltre il tetto prende ancora i brani con punteggio da qui in su


def deduplica(densi: list[dict], grafo: list[dict]) -> list[dict]:
    """Un brano una volta: fra i densi vince la similarità più alta, uno del grafo resta solo se non è fra i densi. I
    canali in cui è comparso restano in `canali`."""
    visti: dict[str, dict] = {}
    for r in densi:
        k = r["chunk_id"]
        if k not in visti or r["similarita"] > visti[k]["similarita"]:
            visti[k] = r
    for r in grafo:
        k = r["chunk_id"]
        if k not in visti:
            visti[k] = r
        elif "grafo" not in visti[k]["canali"]:
            visti[k]["canali"].append("grafo")
    return list(visti.values())


def punteggi(candidati: list[dict], autorevolezza: dict[str, float] | None = None, pesi: dict | None = None) -> None:
    """`score` e `score_components` su ogni candidato, sul posto."""
    pesi = pesi or PESI
    per_persona: dict[str, int] = defaultdict(int)
    per_partito: dict[str, int] = defaultdict(int)
    for r in candidati:
        per_persona[r["speaker"]["uri"] or ""] += 1
        per_partito[r["partito"] or ""] += 1
    max_persona = max(per_persona.values(), default=1)
    max_partito = max(per_partito.values(), default=1)
    for r in candidati:
        persona = r["speaker"]["uri"] or ""
        varieta = 1.0 - 0.5 * per_persona.get(persona, 1) / max_persona
        copertura = 1.0 - 0.5 * per_partito.get(r["partito"] or "", 1) / max_partito
        autorita = (autorevolezza or {}).get(persona, NEUTRO)
        rilievo = r.get("rilievo", NEUTRO)
        r["score"] = (pesi["pertinenza"] * r["similarita"] + pesi["varieta"] * varieta + pesi["copertura"] * copertura
                      + pesi["autorevolezza"] * autorita + pesi["rilievo"] * rilievo)
        r["score_components"] = {"pertinenza": r["similarita"], "varieta": varieta, "copertura": copertura,
                                 "autorevolezza": autorita, "rilievo": rilievo}


def scegli(candidati: list[dict], quanti: int, partiti: list[str] | None, minimo: int = MINIMO_PER_PARTITO) -> list[dict]:
    """Al più `quanti` brani per punteggio, con al più quanti/10 per persona e quanti/3 per partito; poi ogni partito
    atteso sale a `minimo` coi suoi brani migliori, togliendo i peggiori di un partito che resta sopra il minimo."""
    ordinati = sorted(candidati, key=lambda x: x.get("score", 0), reverse=True)
    scelti: list[dict] = []
    per_persona: dict[str, int] = defaultdict(int)
    per_partito: dict[str, int] = defaultdict(int)
    max_persona, max_partito = quanti // 10, quanti // 3
    for r in ordinati:
        if len(scelti) >= quanti:
            break
        persona, part = r["speaker"]["uri"] or "", r["partito"] or ""
        if per_persona[persona] >= max_persona:
            continue
        if per_partito[part] >= max_partito and r.get("score", 0) < SOGLIA_OLTRE_TETTO:
            continue
        scelti.append(r)
        per_persona[persona] += 1
        per_partito[part] += 1

    noti = set(partiti or [])
    presi = {r["chunk_id"] for r in scelti}
    resto: dict[str, list[dict]] = defaultdict(list)
    for r in ordinati:
        if r["chunk_id"] not in presi and (r["partito"] or "") in noti:
            resto[r["partito"]].append(r)
    for part in sorted(noti):
        while per_partito[part] < minimo and resto.get(part):
            cand = resto[part].pop(0)
            if per_persona[cand["speaker"]["uri"] or ""] >= max_persona:
                continue
            if len(scelti) >= quanti:
                vittima = next((r for r in reversed(scelti) if per_partito[r["partito"] or ""] > minimo), None)
                if vittima is None:
                    break                                   # nessun partito che possa cedere: mai oltre `quanti`
                scelti.remove(vittima)
                per_partito[vittima["partito"] or ""] -= 1
                per_persona[vittima["speaker"]["uri"] or ""] -= 1
            scelti.append(cand)
            presi.add(cand["chunk_id"])
            per_partito[part] += 1
            per_persona[cand["speaker"]["uri"] or ""] += 1
    return scelti


def fondi(densi: list[dict], grafo: list[dict], quanti: int, partiti: list[str] | None,
          autorevolezza: dict[str, float] | None = None) -> list[dict]:
    """Deduplica, punteggi e scelta: il cuore della fusione."""
    tutti = deduplica(densi, grafo)
    punteggi(tutti, autorevolezza)
    return scegli(tutti, quanti, partiti)
