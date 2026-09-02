# UX Audit — ParliamentRAG

Data audit: 2 settembre 2026. Branch: `feat/ux-redesign-2026`.
Base: analisi del codice (`frontend/src`), screenshot di produzione desktop (1440×900) e mobile (390×844) su tutte le route pubbliche, contratto SSE del backend (`backend/app/routers/query.py`).

## Executive summary

ParliamentRAG oggi non è un prodotto "slop": la base visiva è già curata (crema #FBFAF8 + blu istituzionale #1B3A5C, Geist + Fraunces, shadcn/Radix, Tailwind v4). Il problema non è estetico, è **strutturale**: il prodotto si presenta come *cinque strumenti separati* invece che come *un motore per capire il Parlamento*.

I tre difetti che pesano di più:

1. **IA tool-centric con etichette in gergo.** La sidebar dice "Ricerca Topic", "Analisi Autorità", "Compasso Ideologico": l'utente deve capire quale strumento usare prima ancora di poter fare una domanda. Ogni tool ha la sua pagina vuota con la sua search bar, il suo empty state e la sua history locale, quattro volte.
2. **Nessuna pagina entità.** Non esistono URL per parlamentari, gruppi, atti o sedute. Un deputato vive solo dentro un modal della pagina ranking; una seduta solo dentro l'infinite scroll della timeline. Niente è citabile o condivisibile a livello di entità.
3. **Verifica potente ma sepolta.** La catena risposta → citazione → intervento → seduta → resoconto ufficiale esiste ed è il vero valore del prodotto, ma passa per modal sovrapposti dentro la chat. La citazione non è ancora la "signature UI" che il prodotto merita.

Cose che invece funzionano e vanno preservate: la landing editoriale, il contratto SSE con progressi reali (nessuna finta progressione), la trasparenza del pannello trace, la pagina /data, il tono istituzionale.

## Product architecture

Stack: Next.js 16 (app router) + React 19, Tailwind v4 con token OKLCH, shadcn/Radix, next-intl (6 lingue, cookie + `?lang=`), lucide-react, cmdk (già in dipendenze, non usato per una palette globale). Backend FastAPI + Neo4j via proxy `/api/[[...path]]`.

Il flusso principale (`/home` → SSE): query → `progress` (step reali) → `experts` → `citations` → `compass` (parallelo alla generazione) → `chunk` streaming → `citation_details` → `experts` aggiornati → `trace` → `complete`. Tutti gli step mostrati corrispondono a operazioni reali del backend: vincolo da mantenere.

## Current routes

| Route | Funzione | In nav | Condivisibile |
|---|---|---|---|
| `/` | Landing editoriale | – | sì |
| `/home` | Chat / ricerca topic | primaria | no (solo via `/chat/[id]`) |
| `/chat/[id]` | Chat salvata | no | sì |
| `/search` | Ricerca atti/interventi | sì | sì (query param) |
| `/ranking` | Autorità per tema | sì | **no** (topic non in URL) |
| `/compass` | Bussola ideologica | sì | **no** (topic non in URL) |
| `/timeline` | Lavori d'Aula | sì | parziale (niente URL seduta) |
| `/explorer` | Cypher sul grafo | **orfana** | sì |
| `/data` | Open data / KG | footer sidebar | sì |
| `/privacy` | Privacy | footer | sì |
| `/iswc` | Survey booth ISWC | QR only (voluto) | sì |
| `/valutazione` | Dashboard valutazione | nascosta (voluto) | sì |

## Current navigation

- Desktop: sidebar blu scuro 260px (collassabile a 70px). Voci: Ricerca Topic; sezione "Strumenti" (Ricerca Atti, Analisi Autorità, Compasso Ideologico, Lavori d'Aula); footer con lingua, impostazioni, "Documentazione" (in realtà un link a GitHub), data aggiornamento dati.
- Mobile: bottom nav a 5 tab + sheet "Altro".
- `/explorer` e `/data` non compaiono nella navigazione principale; la landing non linka l'explorer.
- Nessuna ricerca globale, nessuna command palette (cmdk è installato ma inutilizzato).

## Current UX problems

- **L'utente deve scegliere lo strumento prima della domanda.** Quattro pagine (home, ranking, compass, search) sono di fatto quattro search bar diverse con suggerimenti diversi. Il modello mentale CHIEDI → ESPLORA → ANALIZZA → VERIFICA non è leggibile da nessuna parte.
- **Empty state moltiplicati.** Ranking e compass all'apertura sono pagine vuote con titolo + input: il 70% del viewport è bianco senza guida su cosa aspettarsi come output.
- **History frammentata.** Ogni tool ha la sua cronologia locale (localStorage) con UI leggermente diversa; la chat ha invece history server-side. L'utente non ha un posto unico dove ritrovare il proprio lavoro.
- **"Documentazione" mente.** La voce apre GitHub. Non esiste una pagina metodologia consultabile in-app: l'iter della pipeline è spiegato solo sulla landing.
- **Risultati analitici non condivisibili.** Un ranking di autorità o una bussola calcolata non hanno URL: un giornalista non può passarli a un collega.
- **Ricerca atti: il bottone "Cerca" sembra disabilitato.** Grigio-azzurro spento anche quando cliccabile; la gerarchia del form (chips autore/tipo/periodo dentro card dentro card) è più pesante del necessario.
- **Nessun ponte tra strumenti.** Dopo una risposta in chat non c'è un percorso "vedi la bussola completa su questo tema" / "vedi il ranking completo": compass e experts compaiono come card inline ma non portano alle rispettive viste piene con lo stesso topic.

## Current UI problems

- **Divergenza colori partito**: `config/index.ts` e `CompassCard.tsx` definiscono due palette diverse per gli stessi gruppi (es. FdI #1565C0 vs #0066CC; Lega #4CAF50 vs #008C45, e il verde Lega in config è semanticamente sbagliato). Due viste dello stesso dato usano colori diversi: mina la fiducia.
- **Raggi incoerenti**: `rounded-md` (button/input), `rounded-xl` (card), `rounded-2xl` (chat input), `rounded-[1.75rem]` (bottom nav).
- **Ombre incoerenti**: `shadow-xs`, `shadow-sm`, ombra custom hardcoded sulla bottom nav.
- **Hex sparsi** fuori dai token: ExpertCard, TopicStatsModal, GraphVisualizer, colori evidenziazione citazioni.
- **Componenti monolite**: `MessageBubble.tsx` (958 righe), `ProgressIndicator.tsx` (908 righe, 6 export), `Sidebar.tsx` (300+ righe con dentro settings, lingua, dialogs).
- Card dentro card dentro collapsible nella risposta AI: la lettura dell'answer compete con troppi contenitori.

## Information architecture problems

- Manca il livello **entità**: `/parlamentari`, `/gruppi`, `/atti`, `/sedute` non esistono come pagine. Il backend espone già `/search/deputies?q=`, i dettagli deputato (usati dal modal ranking), le sedute (timeline), i dibattiti e i voti: i dati per pagine entità in larga parte ci sono, manca la superficie.
- I "temi" (topic) sono il concetto centrale del prodotto ma non hanno né URL né pagina: trending e ultimi argomenti sulla home portano a una nuova query, non a un luogo.
- `/explorer` è lo strumento più "research-grade" ed è irraggiungibile dalla navigazione.
- Stats del knowledge graph duplicate (landing `DataStats` vs costanti in `/data`).

## Search UX problems

- Nessuna ricerca globale: cercare "Malavasi" in `/search` trova interventi, ma non c'è modo di arrivare a "la persona Malavasi".
- `/search` non ha ricerca incrementale né preview: form → submit → lista; i filtri sono nel form invece che chips raffinabili sui risultati.
- I suggerimenti sono buoni (entità reali: Eni, Stellantis) ma statici e diversi per ogni pagina.
- La chat non suggerisce riformulazioni quando il gate di rilevanza blocca la domanda (il gate esiste e ha `suggestions` nel payload: vanno rese più actionable).

## Data visualization problems

- **Compass**: il componente è tecnicamente ricco (pan/zoom, ellissi di dispersione, poli spiegati) ma la card inline in chat è 320px di altezza: troppo piccola per uno strumento analitico. Confidence/coverage ci sono nei metadati ma sono relegati a una riga. Colori non coerenti con il resto dell'app (vedi sopra).
- **Ranking**: la lista con barre e percentuali comunica "classifica", non "perché questa persona è autorevole". Il breakdown WHY esiste (speeches/acts/committee/profession/education/role) ma solo nel modal.
- **Hemicycle voti**: buono, da preservare.
- Timeline: le card seduta sono dense, il testo di anteprima è un muro; gerarchia data/numero seduta/eventi debole.

## AI interaction problems

- La risposta AI vive in una "bolla chat" con avatar e contenitori: il contenuto è editoriale (sintesi, posizioni per gruppo, citazioni) ma la forma è da chatbot. Il brief del prodotto è l'opposto: "non è un chatbot".
- La progressione (stepper 8 step) è reale e onesta, buona base; su desktop però occupa molto ed è più "telemetria" che narrazione ("Comprensione della domanda ✓ / Ricerca negli interventi ✓ / …").
- Compass ed esperti arrivano come card intermedie che spingono giù il testo mentre streama: layout shift percepito.
- Balance/bias metrics compaiono con progress bar dentro il messaggio: informazione di metodo mischiata al contenuto.

## Citation / verification UX

Cosa c'è (e va tenuto): citazioni verificate con quote esatta, span evidenziato nel testo pieno, link diretto al resoconto stenografico camera.it costruito da `intervention_id`, badge coalizione, componente del Misto attribuita correttamente, traduzione on-demand, ledger citazioni nel trace.

Problemi:
- La citazione inline è un link markdown «…» poco distinguibile; l'hover non evidenzia il claim associato.
- Il dettaglio apre un **modal centrale** che copre la risposta: si perde il contesto. Serve side drawer (desktop) / bottom sheet (mobile).
- La catena claim → citazione → parlamentare → seduta → fonte è percorribile ma non è *mostrata* come catena: ogni salto è un click in un contenitore diverso.
- Le card citazione in sidebar mostrano similarity score implicitamente (ordinamento) ma non chi/cosa in gerarchia netta: nome, gruppo, data e seduta hanno lo stesso peso visivo.

## Responsive problems

- Mobile complessivamente buono (bottom nav, safe-area, sheet). Problemi puntuali:
  - `/search` mobile: bottone filtri anonimo accanto a "Cerca", periodo nascosto senza indicazione di filtri attivi.
  - Compass su mobile: pan/zoom in un'area piccola con la search bar bottom sovrapposta.
  - Tabelle (valutazione, explorer) non hanno pattern responsive: overflow orizzontale.
  - Modal citazione fullscreen su mobile funziona ma senza gesto di chiusura naturale (manca bottom sheet).

## Accessibility problems

- Base solida: focus-visible ring coerente via CVA, aria su nav/alert/progress, Radix per focus trap, `prefers-reduced-motion` rispettato nei keyframes.
- Da sistemare: contrasto testo muted (oklch 0.5) borderline su crema; il bottone "Cerca" attivo sembra disabilitato (problema anche percettivo); GraphVisualizer canvas senza alternativa testuale; alcune icone-only senza label (history icon in header); gerarchia heading non sempre lineare (h1 multipli su landing); tabella valutazione senza `scope`.

## What should be preserved

- Identità visiva: crema + blu istituzionale + Fraunces per i display. È distintiva, istituzionale, non-AI. Il redesign la raffina, non la sostituisce.
- Contratto SSE e onestà della progressione (solo step reali).
- Verifica citazioni end-to-end e trace "dietro le quinte".
- Landing editoriale (struttura hero con quote reali, garanzie, iter, dati aperti).
- Pagina /data così com'è concettualmente (portale researcher/developer, tema scuro).
- Bottom nav mobile, safe-area, i18n a 6 lingue con `?lang=`.
- Hemicycle voti, schema explorer, dashboard valutazione (interna).
- Tutti gli endpoint e i payload: nessuna modifica al backend.

## What should be redesigned

- **Navigazione**: etichette in linguaggio piano, organizzate per azione (Chiedi / Esplora / Analizza), explorer e dati visibili, command palette ⌘K globale.
- **Home**: gerarchia search-first ("Cosa vuoi sapere del Parlamento?"), suggerimenti, ultimi argomenti + trending, strumenti presentati come modalità di esplorazione in una riga sobria, non protagonisti.
- **Risposta AI**: pagina editoriale (titolo = domanda, sintesi, posizioni, citazioni, fonti) al posto della bolla chat; stepper come narrazione compatta.
- **Citazioni**: signature UI con gerarchia parlamentare/gruppo/data/seduta, hover che evidenzia il claim, side drawer con la catena completa fino alla fonte ufficiale.
- **Ranking**: da classifica a "chi ne sa di più e perché" (WHY visibile senza modal).
- **Compass**: vista piena raggiungibile dalla card in chat, confidence e n. fonti in chiaro, assi spiegati in linguaggio piano.
- **Search**: form più leggero, filtri come chips, bottone primario con stato chiaro.
- **Timeline**: gerarchia editoriale data / seduta / eventi.
- **Cross-linking**: dalla risposta agli strumenti pieni con lo stesso topic; da citazione a seduta in timeline.

## What should be removed

- La voce "Documentazione" che apre GitHub (sostituire con pagina metodologia reale + link GitHub separato nel footer).
- Doppia definizione colori partito (una sola sorgente in config).
- `MobileMenuButton` no-op e altro codice morto di navigazione.
- Duplicazione stats KG landing//data (una sola sorgente, l'hook esistente).
- Contenitori ridondanti nella risposta (card-in-card-in-collapsible).

## What should be introduced

- **Command palette ⌘K** (cmdk già installato): domanda libera + navigazione + deputati via `/search/deputies` + temi suggeriti.
- **`?topic=` su /ranking e /compass**: risultati analitici condivisibili (nessuna modifica backend, solo sync URL).
- **Pagina Metodologia** in-app (contenuti già scritti per la landing: question understanding, retrieval, balance, position mapping, generation, verification).
- **Pagine entità** (roadmap, richiede in parte endpoint nuovi): directory parlamentari e gruppi, dettaglio seduta con URL, dettaglio atto. Da introdurre per fasi: prima le viste costruibili con endpoint esistenti (deputati via search/ranking, sedute via timeline).
- Empty state utili con esempi di domanda concreti e anteprima del tipo di output.

## Priority matrix

**P0 — critico (in questo redesign)**
1. Token unici (colori partito, raggi, ombre, focus) — la fiducia passa dalla coerenza.
2. Navigazione in linguaggio piano + ⌘K + explorer/dati visibili.
3. Home search-first.
4. Citazione: drawer laterale + catena di verifica + hover claim.
5. Risposta AI in forma editoriale (de-chatbotizzare).
6. `?topic=` su ranking e compass.
7. Bottone Cerca e stati del form /search.

**P1 — importante (in questo redesign se il tempo regge, altrimenti subito dopo)**
8. Pagina Metodologia in-app.
9. Ranking come "perché autorevole" (WHY in vista, non solo modal).
10. Cross-link risposta → compass/ranking pieni con stesso topic.
11. Timeline: gerarchia editoriale delle card seduta.
12. Contrasto muted text, label icone-only, heading order.

**P2 — miglioramento (roadmap post-redesign)**
13. Directory parlamentari/gruppi + pagine dettaglio con URL (serve estensione backend per liste complete e profili fuori-topic; da progettare senza breaking changes).
14. URL per seduta (`/sedute/[id]`) e atto.
15. Ricerca globale unificata (persone + atti + temi in un solo indice).
16. Confronto tra due gruppi ("Confronta con…").
17. History unificata cross-strumento.
