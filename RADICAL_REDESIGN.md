# ParliamentRAG — Radical Redesign

Settembre 2026, branch `feat/ux-redesign-2026` (seconda iterazione, dopo il giudizio "troppo conservativa" sulla prima).
Questo documento fissa le decisioni strutturali: cosa cambia nel *prodotto*, non nella vernice.

## 1. Il salto rispetto alla prima iterazione

La prima iterazione ha tenuto: sidebar scura, modello "5 strumenti" (rietichettati), landing con indice degli strumenti, nessuna pagina entità, explorer in navigazione. Questa iterazione li abbandona:

| Prima | Ora |
|---|---|
| Sidebar scura 260px su ogni pagina | **Nessuna sidebar**: barra superiore leggera, contenuto a piena pagina |
| Nav = elenco di strumenti | Nav = **entità del Parlamento** (Parlamentari, Gruppi, Atti, Sedute) + analisi |
| Le entità vivono dentro gli strumenti (modal, righe) | **URL propri**: `/parlamentari/[id]`, `/gruppi/[slug]`, `/sedute/[n]`, `/atti` |
| Explorer in nav ("Knowledge graph") | **Explorer rimosso dall'esperienza**: route legacy non linkata; il grafo è infrastruttura, raccontato in /data |
| Landing con sezione "Gli strumenti" | Landing = **la storia domanda→risposta→prova→fonte** + esplora il Parlamento |
| Metodologia solo sulla landing | **/metodologia** pagina propria (come funziona / dettagli tecnici) |

## 2. Nuovo modello mentale

ParliamentRAG = **un motore per capire il Parlamento**. Quattro azioni: ASK, EXPLORE, UNDERSTAND, VERIFY. L'utente parte dalla domanda o dall'entità, mai dallo strumento. La frase che descrive il prodotto: *"Fai una domanda al Parlamento e segui la risposta fino alla fonte."*

## 3. Application shell: la decisione sulla sidebar

Opzioni valutate:
- **A — Nessuna sidebar, top bar** ✅ scelta. Un prodotto di ricerca si legge come un documento, non come un pannello di controllo. La top bar leggera (56px, su Paper) contiene: simbolo+wordmark, Esplora (menu: Parlamentari, Gruppi, Atti, Sedute), Analizza (menu: Posizioni dei gruppi, Chi ne sa di più), Dati, Metodologia, ⌘K, lingua/impostazioni. Il contenuto occupa tutta la larghezza: le pagine analitiche respirano, le pagine editoriali restano centrate su misura di lettura.
- B — Compact icon rail: mantiene la mentalità tool-launcher, boccia il radicality test.
- C — Navigazione solo contestuale: scopribilità pessima per un prodotto con entità.
- D — Sidebar minimale chiara: ancora un pannello; il problema era il modello, non il colore.

Mobile: bottom nav (pattern già solido) con voci ripensate: **Chiedi · Cerca · Parlamentari · Sedute · Altro** (Gruppi, Posizioni, Chi ne sa di più, Dati, Metodologia, lingua, impostazioni nel foglio).

## 4. Information architecture

```
/                      landing editoriale (storia, non feature list)
/home                  ASK — la domanda (entry point dell'app)
/search                CERCA — interventi e atti (ricerca documentale)
/atti                  ricerca atti (search preimpostata sul tipo documento)
/parlamentari          directory persone      → /parlamentari/[id] research profile
/gruppi                directory gruppi       → /gruppi/[slug] group profile
/sedute                lavori d'Aula (timeline) → /sedute/[n] dettaglio seduta
/ranking?topic=        ANALIZZA — chi ne sa di più (deep-linkabile)
/compass?topic=        ANALIZZA — posizioni dei gruppi (deep-linkabile)
/data                  open data (researcher/developer, invariata nel ruolo)
/metodologia           come funziona (+ dettagli tecnici)
/privacy, /chat/[id]   invariate
/explorer              LEGACY: nessun link in UI, route conservata per sicurezza
/timeline              redirect → /sedute
```

Dati per le pagine entità: **solo endpoint esistenti**. Directory e profili via `POST /graph/query` (read-only, già pubblico, ~300ms misurati in produzione: Deputy espone photo, deputy_card, profession, education; conteggi interventi/atti per singola persona sono economici); interventi via `GET /search/results?deputy_id=|group=`; sedute via endpoint timeline + `Session`/`Debate` sul grafo. Nessuna modifica backend.

## 5. User flows ottimizzati

1. **Nuovo utente**: landing (vede la catena domanda→fonte già nell'hero) → CTA "Fai una domanda" → /home → risposta → click citazione → drawer → resoconto camera.it.
2. **Ricercatore**: /home → ⌘K o /search → filtri chips → risultato → intervento integrale → fonte.
3. **Giornalista**: domanda → sezione posizioni della risposta → /compass?topic= (condivisibile) → citazioni → fonte ufficiale.
4. **Ricerca parlamentare**: tema → /ranking?topic= → click sulla persona → **/parlamentari/[id]** (non più un modal) → interventi → posizioni.
5. **Data researcher**: /home → footer/nav Dati → /data → download RDF → documentazione. (Explorer non è più nel percorso.)

## 6. Wireframe di riferimento

**/home (vuota)** — nessuna sidebar, tutto centrato:
```
[topbar: ◠◠◠ ParliamentRAG   Esplora ▾  Analizza ▾  Dati  Metodologia   ⌘K ⚙]

                    Cosa vuoi sapere del Parlamento?
        [ Chiedi qualcosa al Parlamento…                    → ]
            Sanità · PNRR · Salario minimo · Energia · Giustizia

        ESPLORA IL PARLAMENTO
        Parlamentari →     Gruppi →     Atti →     Sedute →

        Ultimi argomenti in Aula          (dal grafo, come oggi)
```

**/parlamentari/[id]** — research profile, non KPI dashboard:
```
[foto]  NOME COGNOME                      ● Gruppo · ruolo istituzionale
        professione · formazione          ■ Scheda ufficiale Camera
────────────────────────────────────────────────────────────
95 interventi · N atti presentati        (numeri in mono, senza card)
Interventi recenti (lista con data/seduta → fonte)
Chi ne sa di più su… (link a /ranking per i temi in cui compare)
```

**Risultato AI** — research document: DOMANDA (titolo) → RISPOSTA (prosa editoriale) → POSIZIONI (per gruppo) → PROVE (blocchi citazione) → FONTI (resoconti). Struttura già implementata nella prima iterazione, conservata.

## 7. Cosa sparisce dall'esperienza

Explorer come feature (nav, palette, prefissi mobile, link da /data e landing); la parola "strumenti"; la sidebar; le card contenitore non informative; "Documentazione"→GitHub mascherato (ora GitHub è GitHub e la documentazione è /metodologia).

## 8. Cosa resta intatto

Tutta la sostanza scientifica: pipeline SSE reale (nessun progresso finto), citazioni verificate e ledger, authority scoring, bussola con confidence/coverage, hemicycle voti, open data, i18n a 6 lingue, dashboard valutazione (interna).

## 9. Fasi di implementazione (questa iterazione)

1. Shell: AppHeader top-bar su tutte le pagine app, sidebar rimossa; explorer de-linkato.
2. Entità: /parlamentari (+dettaglio), /gruppi (+dettaglio), /atti, /sedute (+dettaglio n).
3. Home ricostruita attorno alla domanda + esplora entità.
4. /metodologia (riusa i contenuti pipeline già tradotti in 6 lingue).
5. Landing: hero-storia (domanda→risposta→prova→fonte), sezione strumenti sostituita da esplora/analizza.
6. QA: build, screenshot desktop+mobile, radicality review (confronto fianco a fianco con produzione).

## 10. Radicality review (criterio di accettazione)

Il confronto produzione vs redesign deve mostrare differenze **strutturali**: shell diversa (niente colonna scura), IA diversa (entità in nav), pagine nuove (4 famiglie di route), home diversa (domanda al centro, niente launcher), landing diversa (storia vs indice strumenti), brand diverso (Emiciclo, Literata, ink/paper). Se una schermata è distinguibile solo per i colori, quella schermata va rifatta.
