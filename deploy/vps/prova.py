"""Prova di ogni servizio del sito su un indirizzo, prima e dopo un rilascio. Solo libreria standard.

    python3 deploy/vps/prova.py http://172.18.0.3:8000              # senza modello: niente spesa
    python3 deploy/vps/prova.py https://www.parliamentrag.it --modello   # anche chat, fascicolo e traduzioni

Esce con 1 se una prova non passa. Il login delle statistiche, se serve, da STATISTICHE_UTENTE e STATISTICHE_PASSWORD.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
MODELLO = "--modello" in sys.argv
UA = "Mozilla/5.0 (prova del rilascio) Safari/605"
esiti: list[tuple[str, bool, str]] = []


def chiama(metodo: str, percorso: str, corpo=None, intestazioni=None, tempo=60):
    dati = json.dumps(corpo).encode() if corpo is not None else None
    h = {"User-Agent": UA, "Accept": "application/json", **({"Content-Type": "application/json"} if dati else {}),
         **(intestazioni or {})}
    r = urllib.request.Request(BASE + percorso, data=dati, method=metodo, headers=h)
    t = time.monotonic()
    try:
        with urllib.request.urlopen(r, timeout=tempo) as risp:
            return risp.status, risp.read(), time.monotonic() - t, dict(risp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), time.monotonic() - t, dict(e.headers)


def prova(nome: str, metodo: str, percorso: str, corpo=None, attesa=200, controlla=None, intestazioni=None, tempo=60,
          lento=10.0):
    """Una richiesta: passa se lo stato è quello atteso, il tempo sotto «lento» e il controllo, se c'è, è vero."""
    try:
        stato, testo, s, _ = chiama(metodo, percorso, corpo, intestazioni, tempo)
    except Exception as e:                          # rete, tempo scaduto
        esiti.append((nome, False, f"{type(e).__name__}: {e}"))
        return None
    nota, ok = f"{stato} in {s:.1f}s", stato == attesa and s < lento
    valore = None
    if ok and controlla:
        try:
            valore = json.loads(testo) if testo[:1] in (b"{", b"[") else testo.decode("utf-8", "replace")
            esito = controlla(valore)
            breve = isinstance(esito, (str, int, float)) and not isinstance(esito, bool) and len(str(esito)) < 60
            ok, nota = bool(esito), nota + (f", {esito}" if breve else "")
        except Exception as e:
            ok, nota = False, f"{nota}, controllo: {type(e).__name__}: {e}"
    if stato != attesa:
        nota += f", atteso {attesa}: {testo[:160]!r}"
    elif s >= lento:
        nota += f", più di {lento:.0f}s"
    esiti.append((nome, ok, nota))
    return valore


def mcp_sito(nome: str, argomenti: dict, controlla, lento=15.0):
    return prova(f"strumento {nome}", "POST", f"/api/mcp/{nome}", argomenti, lento=lento,
                 controlla=lambda d: "errore" not in d and controlla(d["dati"]))


def flusso(nome: str, percorso: str, corpo: dict, finale: str, tempo=300):
    """Una risposta in SSE (chat, fascicolo): passa se arriva l'evento finale e nessun errore."""
    t = time.monotonic()
    try:
        r = urllib.request.Request(BASE + percorso, data=json.dumps(corpo).encode(), method="POST",
                                   headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "text/event-stream"})
        tipi, testo = [], 0
        with urllib.request.urlopen(r, timeout=tempo) as risp:
            for riga in risp:
                riga = riga.removeprefix(b"data:").strip()       # fascicolo in SSE, chat una riga JSON per evento
                if riga.startswith(b"{"):
                    try:
                        e = json.loads(riga)
                    except ValueError:
                        continue
                    tipi.append(e.get("type"))
                    if e.get("type") in ("delta", "chunk"):
                        testo += len(str(e.get("text") or e.get("data") or ""))
        ok = finale in tipi and "error" not in tipi and testo > 100
        esiti.append((nome, ok, f"{time.monotonic() - t:.0f}s, {len(tipi)} eventi, {testo} caratteri, ultimo {tipi[-1:]}"))
    except Exception as e:
        esiti.append((nome, False, f"{type(e).__name__}: {e}"))


def main() -> int:
    # pagine e file del sito
    prova("salute", "GET", "/v1/salute", controlla=lambda d: d["ok"] and d.get("ultima_seduta"))
    prova("home", "GET", "/", controlla=lambda t: "ParliamentRAG" in t and "Organizziamo i dati" in t)
    for f in ("/css/app.css", "/js/base.js", "/js/chat.js", "/js/strumenti.js", "/js/lingua-en.js", "/dati/legale.json"):
        prova(f"file {f}", "GET", f)
    prova("privacy senza Railway e Plausible", "GET", "/dati/legale.json",
          controlla=lambda d: "Hetzner" in json.dumps(d) and "Railway" not in json.dumps(d) and "Plausible" not in json.dumps(d))
    prova("icona", "GET", "/icon.png")

    # dati del sito
    deputati = prova("schede dei deputati", "GET", "/dati/schede/indice.json", controlla=lambda d: len(d["deputati"]) >= 390)
    prova("senatori", "GET", "/dati/senatori.json", controlla=lambda d: len(d["groups"]) >= 6)
    prova("posti del Senato", "GET", "/dati/senato/seats.json")
    leggi = prova("leggi con emendamenti", "GET", "/dati/emendamenti/leggi/index.json", controlla=lambda d: len(d) >= 5, lento=30)
    if leggi:
        prova("emendamenti di una legge", "GET", f"/dati/emendamenti/leggi/{leggi[0]['slug']}.json", lento=30)
    prova("legge elettorale", "GET", "/dati/emendamenti/legge-elettorale.json", lento=30)
    if deputati:
        pid = deputati["deputati"][0]["id"]
        prova("scheda di un deputato", "GET", f"/dati/schede/{pid}.json", lento=30)
        prova("anagrafica di un deputato", "GET", f"/dati/anagrafica/{pid}.json")
    persone = prova("persone", "GET", "/v1/persone?chamber=senato&limit=5", controlla=lambda d: len(d) == 5)
    if persone:
        sid = persone[0]["uri"].rsplit(":", 1)[-1]
        prova("foto di un senatore", "GET", f"/dati/foto/senatori/{sid}.jpg", attesa=200)

    # API pubbliche /v1
    for camera in ("camera", "senato"):
        prova(f"composizione {camera}", "GET", f"/v1/composizione/{camera}", controlla=lambda d: d["members"] > 190)
        prova(f"sedute {camera}", "GET", f"/v1/sedute?chamber={camera}&limit=3", controlla=lambda d: d["total"] > 100)
        prova(f"votazioni {camera}", "GET", f"/v1/votazioni?chamber={camera}&limit=3", controlla=lambda d: d["total"] > 1000)
        prova(f"atti {camera}", "GET", f"/v1/atti?chamber={camera}&limit=3", controlla=lambda d: d["total"] > 1000)
    voti = prova("votazioni", "GET", "/v1/votazioni?limit=1", controlla=lambda d: d["items"])
    if voti:
        prova("una votazione", "GET", f"/v1/votazioni/{voti['items'][0]['uri']}")
    atti = prova("atti", "GET", "/v1/atti?limit=1", controlla=lambda d: d["items"])
    if atti:
        prova("un atto", "GET", f"/v1/atti/{atti['items'][0]['uri']}")
        prova("emendamenti di un atto", "GET", f"/v1/atti/{atti['items'][0]['uri']}/emendamenti", lento=30)
    sedute = prova("sedute", "GET", "/v1/sedute?limit=1", controlla=lambda d: d["items"])
    if sedute:
        prova("una seduta", "GET", f"/v1/sedute/{sedute['items'][0]['uri']}")
    prova("interventi", "GET", "/v1/interventi?q=scuola&limit=3", controlla=lambda d: len(d) == 3)
    prova("documentazione delle API", "GET", "/v1/openapi.json")

    # strumenti del sito (gli stessi del server MCP)
    trovati = mcp_sito("search_parliament", {"query": "salario minimo", "max_results": 3}, lambda d: d["results"])
    for camera in ("camera", "senato"):
        mcp_sito("list_sessions", {"limit": 15, "chamber": camera}, lambda d: d["sessions"])
    s = chiama("POST", "/api/mcp/list_sessions", {"limit": 15, "chamber": "camera"})[1]
    vid = None
    for seduta in json.loads(s)["dati"]["sessions"]:
        v = json.loads(chiama("POST", "/api/mcp/get_session_votes", {"session_id": seduta["id"]})[1])
        if v.get("dati", {}).get("votes"):
            vid = v["dati"]["votes"][0].get("vote_id") or v["dati"]["votes"][0].get("id")
            esiti.append(("strumento get_session_votes", True, f"{len(v['dati']['votes'])} voti in {seduta['id']}"))
            break
    if vid:
        mcp_sito("get_vote_details", {"vote_id": vid}, lambda d: d)
        mcp_sito("get_voted_text", {"vote_id": vid}, lambda d: d)
        mcp_sito("get_vote_hemicycle", {"vote_id": vid}, lambda d: d)
    else:
        esiti.append(("strumento get_session_votes", False, "nessuna seduta con voti fra le ultime 15"))
    if trovati and trovati.get("results"):
        did = trovati["results"][0]["id"].split(".")[0]
        mcp_sito("get_debate", {"debate_id": did}, lambda d: d)

    # server MCP
    h = {"Accept": "application/json, text/event-stream"}
    prova("MCP initialize", "POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "prova", "version": "1"}}},
        intestazioni=h, controlla=lambda t: "serverInfo" in str(t))
    prova("MCP tools/list", "POST", "/mcp", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, intestazioni=h,
          controlla=lambda t: str(t).count('"name"') >= 7 or (len(t["result"]["tools"]) >= 7 if isinstance(t, dict) else False))
    prova("MCP tools/call", "POST", "/mcp", {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "list_sessions", "arguments": {"limit": 1}}}, intestazioni=h, controlla=lambda t: "leg19" in str(t))

    # autorevolezza e verifica (senza modello)
    for camera in ("camera", "senato"):
        prova(f"autorevolezza {camera}", "POST", "/api/autorevolezza", {"topic": "sanità", "chamber": camera}, lento=45,
              controlla=lambda d: len(json.dumps(d)) > 2000)
    prova("verifica", "POST", "/api/verifica", {"question": "Cosa ha detto la Camera sul salario minimo?",
          "answer": "Valentina Ghio ha detto: «Questo percorso non è soltanto un trasferimento di competenze»."}, lento=30)

    # statistiche
    prova("visita", "POST", "/api/visita", {"p": "/#/prova", "w": 1200, "l": "it"}, attesa=204)
    prova("statistiche senza login", "GET", "/statistiche", attesa=401)
    u, pw = os.environ.get("STATISTICHE_UTENTE"), os.environ.get("STATISTICHE_PASSWORD")
    if u and pw:
        a = {"Authorization": "Basic " + base64.b64encode(f"{u}:{pw}".encode()).decode()}
        prova("statistiche con login", "GET", "/statistiche", intestazioni=a, controlla=lambda t: "Statistiche di visita" in t)
        prova("dati delle statistiche", "GET", "/api/statistiche?giorni=7", intestazioni=a, controlla=lambda d: "totali" in d)

    # con il modello: spende qualche centesimo
    if MODELLO:
        flusso("chat", "/api/chat", {"prompt": "Quante votazioni di fiducia ci sono state alla Camera nel 2025?"}, "done")
        flusso("chat in inglese", "/api/chat", {"prompt": "Who spoke about the minimum wage in the Senate?", "locale": "en"}, "done")
        flusso("fascicolo", "/api/fascicolo", {"query": "salario minimo"}, "complete", tempo=600)
        prova("traduzioni", "POST", "/api/traduci", {"testi": ["Disposizioni in materia di salario minimo"]}, lento=30,
              controlla=lambda d: "minimum" in json.dumps(d).lower())

    falliti = [e for e in esiti if not e[1]]
    for nome, ok, nota in esiti:
        print(f"{'ok ' if ok else 'NO '} {nome}: {nota}")
    print(f"\n{len(esiti) - len(falliti)} su {len(esiti)} prove passate su {BASE}")
    return 1 if falliti else 0


if __name__ == "__main__":
    sys.exit(main())
