# ParliamentRAG — Brand Exploration

Settembre 2026. Documento di esplorazione a monte di `BRAND_GUIDELINES.md` (che registra la direzione selezionata). I fogli varianti del logo sono in `assets/brand/`.

## 1. Logo — 5 direzioni (42 varianti su 3 round)

| Direzione | Concept | Esito |
|---|---|---|
| A — Abstract hemicycle | Archi concentrici, segmenti, spazio bianco | Scartata: gli archi concentrici leggono "segnale wi-fi"; l'arco con baseline legge "porta/Ω" |
| B — Hemicycle + nodes | Seggi come nodi disposti ad arco (persone, rete) | Forte a grandi dimensioni, illeggibile a 16px (poltiglia di punti); sopravvive come *idea* nei settori |
| C — Hemicycle + trace | L'arco che scende e si ancora al quadrato-fonte | La famiglia cerchio+arco+gomito legge "cuffie/headset"; le varianti a stelo centrale leggono "ombrello" o "àncora navale" |
| D — Negative space | Emiciclo ricavato in negativo da una forma piena | Letture ambigue (arco/porta, avatar, luna); premium ma non parlamentare |
| E — Evolution del tracciato v1 | Percorso ○—●—■ piegato ad arco | Stessi difetti di C: il glifo di partenza a sinistra + arco = headset |

**Sintesi selezionata — "l'Emiciclo" (B+D):** tre settori d'arco (i gruppi in Aula; i vuoti = i corridoi) + quadrato pieno ad angoli vivi al centro della corda (il podio di chi parla = la fonte a cui tutto si ancora). Conserva dal tracciato v1 il quadrato-fonte (memoria visiva), è riconoscibile come Parlamento senza cupole/colonne/tricolore, e degrada con grazia: a 16px i settori fondono in un arco unico. Test superati: 16/24/32/64/128/512px, favicon, app icon, bianco/nero, monocromia, header app, paper, slide.

## 2. Typography — 5 direzioni

| Direzione | Stack | Valutazione |
|---|---|---|
| 1. Scholarly serif + neutral sans | **Literata + Geist + Geist Mono** ✅ | Serif da lettura digitale nato per contenuti lunghi; regge paper accademico e interfaccia; Geist già in codebase (zero regressioni); tripartizione contenuto/strumento/dato |
| 2. Tutta sans "Linear-like" | Geist ovunque | Pulita ma indistinguibile da mille SaaS; perde la voce editoriale che il prodotto ha già |
| 3. Grotesk display | Space Grotesk + IBM Plex Sans | Carattere "tech contemporaneo" ma scivola verso startup AI; Space Grotesk è ovunque nel 2026 |
| 4. Editoriale classico | Tiempos/GT Sectra + Inter | Bellissimo su carta, licenze commerciali, e "quotidiano" più che "istituto di ricerca" |
| 5. IBM Plex famiglia completa | Plex Sans + Plex Serif + Plex Mono | Coerente e libera, ma identità fortemente IBM/Carbon; poco distintiva |

Selezione: **1**. Ruoli: Literata = brand/editoriale (titoli, domanda, risposte, quote); Geist = UI; Geist Mono = dato (numeri, date, ID, score).

## 3. Color — 5 direzioni

| Direzione | Palette | Valutazione |
|---|---|---|
| 1. Ink + Paper + Blu Archivio ✅ | quasi-nero freddo su crema caldo, un accento blu desaturato funzionale | Neutralità politica per costruzione (monocromia dominante); continuità con la carta/resoconto; l'accento è archivio, non partito |
| 2. Graphite freddo puro | grigi neutri + accento acciaio | Neutrale ma anonimo; perde il calore "carta" che distingue il prodotto dai SaaS scuri |
| 3. Ink + verde istituzionale | accento verde profondo | Il verde è Lega nel paesaggio italiano: bocciato per neutralità |
| 4. Bordeaux Camera | accento bordeaux (aula di Montecitorio) | Elegante ma il rosso scuro slitta verso PD/istituzione politica; tenuto solo come colore d'errore |
| 5. Dark-first | ink come superficie dominante | Autorevole su slide, faticoso per lettura lunga; il prodotto è lettura |

Selezione: **1**, con i colori dei gruppi come *semantic data colors* definiti una sola volta (`PARTY_PALETTE`) e mai usati come colori d'interfaccia.

## 4. Tre sistemi completi valutati

**Sistema A — "L'Archivio Vivo"** ✅ (selezionato)
Concept: il resoconto stenografico reso interrogabile; il brand è l'atto di risalire alla carta. Logo: l'Emiciclo. Type: Literata/Geist/Mono. Colori: ink/paper/Blu Archivio. Forme: filetti, angoli vivi per i documenti, nodi/tracciati solo con significato. Motion: la pipeline che si disegna come tracciato tra nodi reali. UI: blocchi-citazione con filetto, drawer-fonte, hemicycle voti. Forza: brand=prodotto (la verificabilità è la firma visiva); regge paper e conferenza. Debolezza: chiede disciplina, la quiete può sembrare austerità.

**Sistema B — "La Rete delle Voci"**
Concept: il Parlamento come rete di persone e relazioni. Logo: costellazione di nodi ad emiciclo. Type: grotesk display + sans. Colori: graphite + accento acceso. Motion: connessioni che si accendono. Forza: fotogenico, "tech". Debolezza: indistinguibile dal paesaggio graph/AI; promette social-network più che prova documentale; il nodo-grafo è il *mezzo*, non il valore.

**Sistema C — "Il Quotidiano Parlamentare"**
Concept: un giornale che si scrive dai resoconti. Logo: testata tipografica pura (wordmark). Type: serif editoriale forte ovunque. Colori: bianco/nero + un colore di testata. Forza: leggibilità e gravitas. Debolezza: si percepisce *testata giornalistica con linea editoriale*, l'opposto della neutralità evidence-based; il vincolo del brief lo esclude.

## 5. Wordmark

"ParliamentRAG" in Literata SemiBold, tracking leggermente stretto, nessuna separazione grafica o cromatica di "RAG". Lockup: simbolo+wordmark orizzontale (header), stacked (poster/slide), solo simbolo (favicon/avatar/watermark), solo wordmark (contesti con simbolo già presente).

## 6. Implicazioni UI del sistema selezionato

- Shell chiara senza pannelli scuri: l'app è una pagina di lettura, la gerarchia la fa la tipografia.
- La citazione è il componente-firma (filetto + angoli vivi + ■ ancora alla fonte).
- I numeri sono sempre dato (mono), mai decorazione KPI.
- Confidence/coverage sempre dichiarate accanto ai risultati calcolati.
- Conferenza: slide Paper con simbolo mono, pattern a settori come divisore, QR con modulo ■.
- GitHub: social preview simbolo su Ink + tagline EN; README con variante light/dark.
