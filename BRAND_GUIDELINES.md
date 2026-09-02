# ParliamentRAG — Brand Guidelines

Versione 1.0 — settembre 2026. Branch: `feat/ux-redesign-2026`.
Documento normativo per identità visiva e verbale. Le scelte implementative (token, componenti) sono in `DESIGN_SYSTEM.md`.

---

## 1. Brand strategy

**Cosa è ParliamentRAG in una frase:**

> ParliamentRAG ti permette di fare una domanda al Parlamento italiano e di risalire da ogni risposta alle parole realmente pronunciate in Aula.

Questa frase è comprensibile a chi non sa cosa sia RAG. È il messaggio primario: tutto il resto (knowledge graph, authority scoring, bussola) è approfondimento.

**Positioning:** *Parliamentary intelligence infrastructure* — infrastruttura di conoscenza sul Parlamento. Non un chatbot, non un sito istituzionale, non una testata: uno strumento di ricerca con garanzie di verificabilità.

**Il problema che il brand risolve:** il livello scientifico del progetto è alto, ma la percezione oscilla tra "progetto universitario" e "chatbot". Il brand deve spostare la percezione su: autorevolezza, precisione, trasparenza, indipendenza, ricerca.

## 2. Positioning

Tre coordinate che ci distinguono dai vicini di categoria:

- Rispetto a un **chatbot AI**: ogni affermazione è ancorata a una fonte ufficiale; il processo è ispezionabile (trace).
- Rispetto a un **sito istituzionale**: si parte dalla domanda, non dal documento; il linguaggio è piano.
- Rispetto a una **testata giornalistica**: nessuna linea editoriale; le posizioni sono calcolate e dichiarate con confidenza e copertura, non raccontate.

## 3. Personality

Intelligent, precise, calm, authoritative, transparent, curious, independent, modern, human, research-driven.

Non è: loud, political, aggressive, corporate, playful, overly futuristic, generic AI.

Regola pratica: se un elemento visivo o verbale potrebbe stare nella landing di una startup AI generica, non appartiene a ParliamentRAG.

## 4. Archetype

**The Sage** (primario) — il prodotto esiste per far capire, non per persuadere. Ogni risposta espone le proprie prove.
**The Explorer** (secondario) — l'utente scava: da un claim a un intervento, a una seduta, al grafo.
The Architect resta come carattere strutturale (rigore del sistema, del grafo, della pipeline) ma non guida il tono: un brand "architetto" diventerebbe corporate.

In pratica: voce da Sage, interazioni da Explorer, struttura da Architect.

## 5. Naming

Valutazione di "ParliamentRAG":

| Criterio | Giudizio |
|---|---|
| Comprensibile | "Parliament" sì; "RAG" solo per pubblico tecnico |
| Memorabile | Sì (insolito, corto) |
| Internazionale | Sì (inglese) |
| Troppo tecnico | "RAG" sì, ma è anche un segnale di serietà per il pubblico accademico |
| Adatto a non tecnici | Parziale: serve la tagline a fare da traduzione |
| Adatto a ricercatori | Sì, ed è già capitale accumulato: demo ISWC 2026, DOI Zenodo, paper, GitHub |
| Può diventare un brand | Sì |

**Decisione: mantenere ParliamentRAG.** Rinominare brucerebbe il capitale accademico (citazioni, DOI, repository) proprio prima della conferenza. La debolezza ("RAG" opaco ai non tecnici) si mitiga verbalmente: la tagline e il primo messaggio spiegano il prodotto senza mai richiedere la definizione di RAG.

Grafia: sempre `ParliamentRAG` (P e RAG maiuscoli, nessuno spazio). Mai "Parliament RAG", "ParliamentRag", "PRAG".

## 6. Brand architecture

Un solo brand. Le aree del prodotto sono descrittori, non sotto-brand:

- ParliamentRAG (prodotto)
- ParliamentRAG Data (portale open data — già esistente come /data)
- ParliamentRAG MCP (connettore — già pubblicato)

Non creare altri sotto-brand. "Search", "Research" ecc. restano nomi di funzioni, in minuscolo, nella lingua dell'interfaccia.

## 7. Tagline

Primaria (IT / EN):

> **Dalla domanda alla fonte.**
> **From question to source.**

È il concetto centrale del brand (vedi §8) in quattro parole, comprensibile a chiunque, non slogan.

Alternative valutate (utilizzabili in contesti secondari):

1. Il Parlamento, interrogabile.
2. Ogni risposta ha una fonte.
3. Ciò che il Parlamento ha detto davvero. *(già in uso sulla landing: mantiene continuità come claim editoriale)*
4. Chiedi. Verifica. Risali alla fonte.
5. Capire il Parlamento, parola per parola.
6. Il dibattito parlamentare, ricercabile e verificabile.
7. La XIX Legislatura, parola per parola.
8. Parliament, searchable and verifiable.
9. Ask Parliament. Follow the evidence.
10. Every answer, anchored to the record.
11. Understand Parliament, word for word.

Scartate le direzioni "Ask the Parliament." (troppo chatbot) e qualsiasi formula con "AI/intelligenza artificiale" nella tagline (il valore è la verificabilità, non la tecnologia).

## 8. Core brand idea — IL TRACCIATO

Il concetto centrale, scelto tra tre direzioni (vedi §20):

> **Ogni risposta è un percorso tracciabile: domanda → risposta → prova → fonte.**

"Il Tracciato" unisce Parlamento (il resoconto stenografico è letteralmente *la traccia* di ciò che è stato detto), conoscenza (il grafo), prova (il ledger delle citazioni) e ricerca (il retrieval è un percorso nel grafo). È astratto abbastanza da durare, concreto abbastanza da disegnarsi.

Da questo concetto discendono: il simbolo (§9), il linguaggio grafico (§13), il motion (§16), il trust design (§17).

## 9. Logo

### Simbolo — "il Tracciato"

Tre elementi su una diagonale, collegati da una linea:

```
  ○
   \
    ●
     \
      ■
```

- **Cerchio aperto** = la domanda (aperta, umana)
- **Nodo pieno** = il passaggio nel grafo di conoscenza
- **Quadrato pieno** = la fonte (chiusa, ancorata, ufficiale)

Geometria di riferimento (griglia 24×24):
- cerchio: centro (5.5, 5.5), r 2.6, stroke 2, senza riempimento
- linea: da (7.4, 7.4) a (17, 17), stroke 2, round cap, interrotta dal nodo
- nodo: cerchio pieno r 1.8 centro (11.5, 11.5)
- quadrato: 5×5, angoli vivi, centro (17.5, 17.5)

Il simbolo vive da solo: favicon, app icon, avatar social, watermark, logo su paper. A 16px il tracciato si semplifica: cerchio, nodo e quadrato senza linea (la diagonale resta leggibile per allineamento).

Cosa NON è: non è una cupola, non è un cervello, non è un circuito, non è un tricolore, non contiene "RAG".

### Sistema

| Versione | Composizione | Uso |
|---|---|---|
| Primary | simbolo + wordmark orizzontale | header sito, documenti |
| Secondary | simbolo sopra wordmark (stacked) | poster, slide title |
| Symbol | solo simbolo | favicon, avatar, watermark |
| Wordmark | solo "ParliamentRAG" | contesti dove il simbolo è già presente |
| Monochrome | tutto in Ink oppure tutto in Paper | stampa b/n, timbri, paper accademici |
| Small-size | simbolo semplificato (3 elementi, no linea) | ≤20px |

Wordmark: "ParliamentRAG" in Literata SemiBold, tracking leggermente negativo, nessuna enfasi cromatica su "RAG". Colori: Ink su Paper; inversione Paper su Ink per fondi scuri. Il simbolo può usare l'accento Blu Archivio sul solo quadrato (la fonte) quando serve un punto focale; in contesti formali resta monocromo.

Clear space: altezza del quadrato su tutti i lati. Dimensione minima lockup: 24px di altezza.

## 10. Typography

Quattro ruoli, tre famiglie:

| Ruolo | Font | Perché |
|---|---|---|
| Brand + Editorial (display, titoli, risposte lunghe) | **Literata** | Serif progettato per la lettura digitale, carattere scholarly senza essere antiquato; regge sia l'interfaccia AI sia una pubblicazione scientifica. Sostituisce Fraunces (troppo "display", diventato un default estetico). |
| UI (navigazione, controlli, form, metadata) | **Geist** | Già in uso, neutro e preciso; nessun motivo di sostituirlo. |
| Data (numeri, ID, codice, Cypher, RDF) | **Geist Mono** | Tutti i numeri tabellari e gli identificatori in mono: precisione percepita e allineamento. |

Gerarchia tipografica: i titoli editoriali (domanda dell'utente, sezioni della risposta, titoli di pagina) in Literata; tutto ciò che è strumento (bottoni, filtri, nav) in Geist; tutto ciò che è dato (score, date in tabelle, ID seduta) in Geist Mono. Questa tripartizione È il brand tipografico: contenuto/strumento/dato sempre distinguibili a colpo d'occhio.

## 11. Colors

Principio: **la neutralità è monocromia**. Un prodotto che analizza la politica non può avere un colore "di partito" come protagonista. Il brand è inchiostro su carta; il colore compare solo quando ha una funzione.

| Token | Valore (OKLCH) | Ruolo |
|---|---|---|
| Ink | `oklch(0.24 0.015 260)` | Testo primario, simbolo, superfici scure |
| Paper | `oklch(0.98 0.004 85)` | Sfondo (continuità con l'attuale crema) |
| Graphite 1–5 | scala neutra fredda | Testo secondario, bordi, superfici |
| **Blu Archivio** (accent) | `oklch(0.42 0.08 255)` | Unico accento: azioni primarie, link, focus, stato attivo |
| Verified | `oklch(0.52 0.1 155)` | Solo sigilli di verifica e fonti confermate |
| Warning | `oklch(0.72 0.13 80)` | Avvisi (bassa copertura, dati parziali) |
| Error | `oklch(0.5 0.16 20)` | Errori (bordeaux, non rosso squillante) |

Ruoli derivati: Background=Paper, Surface=Paper +1 step, Border=Graphite 4, Text=Ink, Muted=Graphite 2 (contrasto ≥ 4.5:1 su Paper, correzione rispetto all'attuale).

**Neutralità politica:** il Blu Archivio è desaturato e scuro, lontano dall'azzurro FI, dal blu elettorale e da qualunque colore identitario di partito; è la tinta degli archivi e delle istituzioni, non di una parte. Verde, giallo, rosso e arancio saturi (Lega, M5S, PD, Azione) non compaiono MAI come colori di interfaccia: esistono solo come colori-dato nella palette gruppi (§14), definita una volta sola.

## 12. Verbal identity

**Tono:** chiaro, preciso, sobrio, intelligente. Frasi brevi, verbi concreti, mai esclamativi. L'interfaccia dà del "tu" senza entusiasmo artificiale.

**CTA language:** verbo + oggetto. "Fai una domanda", "Apri la fonte", "Esplora le sedute", "Scarica i dati". Mai "Scopri di più", "Inizia ora!", "Prova la magia".

**Vocabolario da preferire:** fonte, intervento, seduta, resoconto, posizione, gruppo, parlamentare, prova, contesto, verificato, copertura, tema, Aula.

**Da evitare:** insight, disruption, next-gen, revolutionary, "AI magic", "powered by AI", cutting-edge, seamless, empower. La parola "AI" si usa con parsimonia e sempre insieme alla garanzia ("risposte AI collegate alle fonti ufficiali"), mai da sola come valore.

**Linguaggio tecnico:** vive in metodologia e documentazione ("semantic retrieval", "authority scoring"), non nell'interfaccia principale ("Cerca negli interventi", "Chi ne sa di più").

**Voce editoriale:** le risposte del sistema sono referti, non conversazioni. Niente "Ecco cosa ho trovato!", niente scuse prolisse; in caso di limiti, dichiarazioni asciutte ("Copertura bassa su questo tema: 12 interventi da 4 gruppi").

## 13. Shape language + graphic language

Grammatica geometrica derivata dal Tracciato:

- **Nodi** (cerchi pieni piccoli), **linee** (stroke 1–2px), **ancore** (quadrati pieni): gli unici elementi decorativi ammessi, sempre con significato (un percorso, una connessione, una fonte).
- **Hairline rules** orizzontali per separare, al posto delle card, quando la gerarchia lo consente.
- **Rettangoli** ad angolo moderato (8px) per superfici funzionali; **angoli vivi** per tutto ciò che rappresenta "fonte/documento" (il quadrato del simbolo si riflette nei blocchi citazione).
- Griglie visibili solo dove organizzano dati reali.

Vietato: pill ovunque, cerchi decorativi, blob, gradienti scenografici, glassmorphism.

Il pattern proprietario "tracciato" (sequenze ○—●—■ orizzontali o diagonali) può marcare: intestazioni di sezione su slide/poster, divisori su carta intestata, social card, README. Usato con parsimonia: una occorrenza per artefatto.

## 14. Data visualization brand

- Base monocroma: assi, griglie e testo in Graphite; mai bordi neri pieni.
- **Palette gruppi parlamentari: una sola, in `frontend/src/config`**, usata identica da compass, ranking, hemicycle, grafo. I colori partito sono colori-dato: compaiono solo dove identificano un gruppo. (Oggi esistono due palette divergenti: bug di brand oltre che di codice.)
- Numeri sempre in Geist Mono. Score 0–100 senza decorazione: numero grande + barra sottile senza track pieno.
- Confidenza e copertura sempre dichiarate accanto al grafico (n. interventi, n. gruppi, varianza/coverage): la trasparenza è parte del linguaggio visivo.
- Hemicycle: mantiene i colori semantici di voto (favorevole/contrario/astenuto) già in uso.
- Knowledge graph: nodi per tipo con la stessa palette-dato, sfondo Paper o Ink, mai colori arbitrari.

## 15. Iconography

- Famiglia unica: **Lucide** (già in uso, coerente con Geist).
- Stroke 1.75 uniforme, dimensioni 16/20/24, angoli round di libreria.
- Niente emoji nell'interfaccia, nei testi di sistema e nella documentazione.
- Icone sempre accompagnate da label o `aria-label`.

## 16. Motion branding

Il movimento rappresenta il tracciato: **connessione, recupero, verifica**.

- Durate 150–250ms, easing `cubic-bezier(0.16, 1, 0.3, 1)`.
- Ammesso solo per: apertura drawer/popover, progressione reale della pipeline, evidenziazione claim↔citazione, transizioni dei grafici, hover di stato.
- Firma di brand: la progressione della pipeline si disegna come una linea che avanza tra nodi (gli step reali del backend) fino all'ancora finale. Nessuna animazione decorativa infinita.
- `prefers-reduced-motion`: tutto degrada a stati statici.

## 17. Trust design

Linguaggio visivo della verificabilità (il cuore del brand):

| Concetto | Trattamento |
|---|---|
| Citazione | Blocco ad angoli vivi con filetto sinistro Ink; quote in Literata corsivo; metadata in Geist Mono |
| Fonte ufficiale | Link con quadrato pieno ■ come glifo (l'ancora del simbolo) + "Resoconto stenografico" |
| Verificato | Sigillo nel colore Verified, solo quando il backend conferma la verifica |
| Confidence/coverage | Sempre testuale e numerica accanto al risultato, mai solo un colore |
| Metodologia | Link visibile ovunque compaia un risultato calcolato |

Regola: mai vestire di "verificato" ciò che il sistema non ha verificato. Il trust design rende visibili le garanzie reali del backend, non ne aggiunge di estetiche.

## 18. Digital applications

- **Landing** = massima espressione del brand: simbolo, headline editoriale in Literata, tagline, interazione di ricerca reale, catena domanda→risposta→prova→fonte mostrata, non raccontata.
- **/home** = stesso brand, densità maggiore: l'utente non deve percepire un salto tra "sito" e "app".
- Gerarchia visiva ovunque: 1 brand, 2 azione (la domanda), 3 informazione (la risposta), 4 prova (citazioni), 5 metadata.
- Empty state, loading, error: voce §12, progressione §16 (solo step reali).

## 19. Conference / GitHub / icone

**Conferenza (ISWC 2026, Bari):**
- Slide standard: Paper background, simbolo in alto a sinistra, titolo Literata, un pattern tracciato come divisore, QR in basso a destra con il quadrato ■ come modulo di riconoscimento.
- Composizione poster/badge: simbolo grande monocromo + wordmark + tagline + one-liner (§1) + QR.
- Tutto deve funzionare in bianco e nero (stampa atti conferenza).

**GitHub:** social preview con simbolo su Ink + tagline EN; README con logo SVG in testa (variante light/dark via `picture`), badge sobri, niente emoji.

**Favicon / app icon:** simbolo small-size (senza linea) su Paper per favicon 16/32/64; su Ink con margini generosi per 180/512 (maskable). Il quadrato ■ resta l'elemento riconoscibile anche a 16px.

## 20. Le tre direzioni creative valutate

**A — The Knowledge Network.** Concept: il Parlamento come grafo. Logo: cluster di nodi. Colori: graphite + verde dato. Forza: verità tecnica (il KG esiste). Debolezza: indistinguibile da mille brand "network/AI"; non comunica la verificabilità, che è il differenziante; il grafo è mezzo, non fine.

**B — The Evidence Trace.** Concept: il percorso domanda→fonte. Logo: il Tracciato ○—●—■. Colori: ink/paper + Blu Archivio funzionale. Forza: rappresenta l'unica cosa che nessun concorrente può dire (ogni parola risale al resoconto); genera da solo motion, trust design e pattern grafico; neutrale per costruzione (monocromia). Debolezza: più concettuale, richiede coerenza d'uso per sedimentare.

**C — The Parliamentary Interface.** Concept: architettura d'Aula astratta (archi di emiciclo). Logo: arcature geometriche. Forza: immediatamente "parlamento". Debolezza: scivola nel cliché istituzionale (cupole/colonne sono vietate dal brief e gli archi ci arrivano vicino); comunica il soggetto, non il valore; rischio percezione "sito della PA".

**Selezione: B.** È l'unica direzione in cui brand = prodotto: il simbolo disegna letteralmente ciò che il sistema fa. A e C descrivono rispettivamente il *come* e il *dove*; B descrive il *perché fidarsi*.

## 21. Do / Don't

**Do**
- Monocromia prima, colore solo funzionale.
- Literata per contenuto, Geist per strumento, Mono per dato.
- Mostrare sempre copertura e limiti dei risultati.
- Simbolo da solo dove lo spazio è poco.
- Bianco e nero come test di ogni artefatto.

**Don't**
- Colori di partito nell'interfaccia.
- Cupole, colonne, tricolore, cervelli, circuiti, robot.
- "RAG" enfatizzato graficamente nel wordmark.
- Gradienti scenografici, glow, glassmorphism, emoji.
- Slogan entusiasti o lessico "AI magic".
- Vestire di verificato ciò che non lo è.

## 22. Design test (checklist finale)

- [ ] Senza il testo, il simbolo è riconoscibile? (○—●—■ su diagonale: sì, non esiste nel paesaggio civic-tech italiano)
- [ ] In bianco e nero regge? (nato monocromo)
- [ ] A 16px? (versione small-size dedicata)
- [ ] Su paper accademico? (monocromo, serif scholarly)
- [ ] Su slide e poster? (pattern tracciato + composizione §19)
- [ ] Screenshot dell'app riconoscibile? (tripartizione tipografica + blocchi citazione ad angolo vivo + filetto)
- [ ] Il citation component è brand? (§17: è l'applicazione più diretta del simbolo)
- [ ] Neutralità percepita? (monocromia dominante, colori partito solo come dato)
