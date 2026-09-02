# ParliamentRAG — Design System

Versione 1.0 — settembre 2026. Implementa `BRAND_GUIDELINES.md` nel frontend (Tailwind v4, token OKLCH in `frontend/src/app/globals.css`, componenti shadcn/Radix in `frontend/src/components/ui`).

## Typography

| Ruolo | Font | Token | Uso |
|---|---|---|---|
| Editorial/display | Literata (next/font, `--font-display`) | `font-display` | Titoli pagina, domanda utente, heading risposta, quote citazioni (corsivo) |
| UI | Geist (`--font-geist-sans`) | default | Nav, bottoni, form, label, body funzionale |
| Data | Geist Mono (`--font-geist-mono`) | `font-mono` | Numeri tabellari, score, date in metadata, ID, Cypher/RDF |

Scala (desktop → mobile):
- Display: `text-4xl md:text-5xl` Literata 600, `tracking-tight`
- H2 sezione: `text-2xl` Literata 600
- H3: `text-lg` Geist 600
- Body lettura: `text-base leading-relaxed max-w-[68ch]`
- Body UI: `text-sm`
- Metadata/caption: `text-xs` (mono quando è dato)

Regole: mai Literata su controlli; mai numeri proporzionali in tabelle; niente `<br>` nei titoli; corsivo con descender → `leading-[1.1]` minimo.

## Colors

Definiti una sola volta in `globals.css` (`@theme`), nessun hex nei componenti.

```
--background      oklch(0.98 0.004 85)    /* Paper */
--foreground      oklch(0.24 0.01 220)    /* Ink neutro */
--card / surface  oklch(1 0 0)            /* superficie rialzata */
--muted           oklch(0.94 0.006 85)
--muted-foreground oklch(0.45 0.012 220)  /* >=4.5:1 su Paper */
--border          oklch(0.88 0.008 85)
--primary         oklch(0.45 0.07 205)    /* Petrolio: azioni, link, attivo */
--primary-foreground oklch(0.98 0.004 85)
--ring            oklch(0.45 0.07 205)
--success         oklch(0.52 0.1 155)     /* solo verifica */
--warning         oklch(0.72 0.13 80)
--destructive     oklch(0.5 0.16 20)      /* bordeaux */
--sidebar         Ink (nav scura conservata come superficie brand)
```

**Migrazione settembre 2026 (via il vecchio blu).** Il blu istituzionale `#1B3A5C` e ogni suo derivato (token hue 250-260, tailwind `blue-*` di brand, ombre tinte, `theme_color` del manifest, crema `#E8DCC8` del logo) sono rimossi: accento unico Petrolio, superfici scure in Ink neutro (`bg-foreground`), logo in Paper/Ink. Audit: `grep -rn "1B3A5C|3B82F6|E8DCC8"` deve restituire zero. Eccezioni ammesse perche' colori-dato, non brand: blu/indigo del pannello survey A/B (Sistema A vs B nel confronto cieco) e i badge categorici dei tipi di atto in ResultsList.

Palette gruppi parlamentari: **solo** in `src/config/index.ts` (`POLITICAL_GROUP_COLORS`); compass, ranking, hemicycle, grafo la importano. Vietato definire colori partito altrove.

## Spacing

Scala: 4, 8, 12, 16, 24, 32, 48, 64, 96. Sezioni di pagina: `py-12` (app) / `py-24` (landing). Gap standard liste: 8–12. Padding card/blocchi: 16–24. Form: `gap-2` label/input, `gap-4` tra campi.

## Radius

`--radius: 8px`. Sistema documentato:
- Superfici e input: 8px (`rounded-lg`)
- Bottoni: 8px
- Chips/badge filtro: pill (unica eccezione, per riconoscibilità del filtro)
- Blocchi citazione e ancore fonte: **angoli vivi** (0) — linguaggio del documento
- Vietati raggi custom arbitrari (`rounded-[1.75rem]` ecc.)

## Shadows

Due livelli: `shadow-sm` (superfici sticky/nav), `shadow-lg` tinta Ink al 10% (drawer, popover, modal). Nient'altro. Le card in flusso non hanno ombra: bordo o filetto.

## Buttons

- Primary: bg `--primary`, testo Paper. Stato disabilitato: `opacity-50` + cursore, MAI un colore intermedio ambiguo (bug attuale del "Cerca").
- Secondary: bordo `--border`, testo Ink.
- Ghost: solo testo, per azioni terziarie.
- `:active`: `scale-[0.98]`. Focus: ring 3px `--ring/50`.
- Label max 3 parole, un solo intent per pagina (un solo "Cerca").

## Inputs / Search

- Label sopra, helper sotto, errore sotto in `--destructive`. Mai placeholder-as-label.
- Search primaria (home): input grande (h-14), Literata per il testo digitato no — testo utente in Geist; placeholder "Chiedi qualcosa al Parlamento…".
- Command palette ⌘K (cmdk): gruppi Temi / Deputati / Strumenti; deputati via `/search/deputies?q=`.
- Filtri: chips pill che aprono popover (desktop) / bottom sheet (mobile); i filtri attivi restano visibili come chips valorizzate.

## Navigation

- Desktop: sidebar Ink 260px/70px (conservata), voci in linguaggio piano:
  - **Chiedi** (home), poi gruppo **Esplora**: Interventi e atti (search), Lavori d'Aula (timeline), Grafo (explorer); gruppo **Analizza**: Chi ne sa di più (ranking), Posizioni dei gruppi (compass).
  - Footer: Dati aperti, Metodologia, lingua, impostazioni, data aggiornamento.
- Mobile: bottom nav 5 voci + sheet "Altro" (conservata, etichette allineate).
- ⌘K raggiungibile ovunque (icona + scorciatoia).

## Cards

Ridurre: le card sono per elementi interattivi ripetuti (risultato di ricerca, seduta). Contenuti in flusso usano sezioni + hairline (`border-t`) + spazio. Vietato card-in-card oltre un livello.

## Citation (signature component)

Blocco ad angoli vivi, filetto sinistro 2px Ink:

```
│ Ilenia Malavasi · PD                    [gruppo: pallino colore-dato]
│ 3 giugno 2026 · Seduta 668              (Geist Mono, muted)
│ «testo citato…»                          (Literata corsivo)
│ ■ Apri il resoconto ufficiale            (link con glifo ancora)
```

- Hover sulla citazione inline → evidenzia il claim collegato nel testo (e viceversa).
- Click → **drawer laterale** (desktop) / **bottom sheet** (mobile), mai modal centrale: la risposta resta visibile.
- Drawer: catena completa Claim → Citazione (quote evidenziata nel testo integrale) → Parlamentare → Gruppo → Seduta → link resoconto camera.it. Traduzione on-demand conservata.
- Sigillo "verificata" (colore success) solo se `verified: true` dal backend.

## Drawer / Sheet

Radix Sheet esistente: right-side desktop (max-w-lg), bottom mobile con handle. Motion 200ms. Un solo livello di drawer; dal drawer si naviga, non si impila.

## Tables

Header `text-xs uppercase` Geist, righe `border-b` singolo, numeri right-aligned mono. Mobile: righe → card verticali con coppie label/valore. Tabelle dense (explorer, valutazione) scrollabili con colonna chiave sticky.

## Charts

Regole in §14 delle brand guidelines. Operativo: assi/griglie Graphite, colori solo per gruppi (dalla config), numeri mono, confidenza e copertura sempre visibili come testo, tooltip con bordo `--border` senza ombra pesante. Barre score: sottili, senza track pieno di sfondo scuro.

## States

- **Loading AI:** stepper reale della pipeline come tracciato (nodi che si riempiono, linea che avanza): "Comprensione della domanda ✓ → Ricerca negli interventi ✓ → Selezione delle fonti ● → Verifica ○". Solo step provenienti dagli eventi SSE `progress` (mai finti).
- **Loading dati:** skeleton nella forma del layout finale; mai spinner generici salvo azioni puntuali.
- **Empty:** una frase + un esempio concreto cliccabile ("Prova: Come si sono posizionati i gruppi sulla riforma fiscale?").
- **Error:** "Non siamo riusciti a completare questa ricerca." + [Riprova]; mai "Something went wrong".
- **Gate di rilevanza:** blocco con suggerimenti actionable (payload `gate.suggestions`).

## Responsive

Breakpoint standard Tailwind. Contenuto: `max-w-3xl` (lettura), `max-w-7xl` (liste/analisi). Hero: `min-h-[100dvh]` mai `h-screen`. Safe-area già gestita (conservare). Compass mobile: fullscreen dedicato, search non sovrapposta al grafico. Citation mobile: bottom sheet.

## Accessibility

WCAG AA: muted ≥4.5:1 (corretto in token), focus-visible ring ovunque, `aria-label` su tutte le icone-only, heading order lineare per pagina, `prefers-reduced-motion` su ogni animazione, tabelle con `scope`, canvas (grafo) con descrizione testuale.

## Migrazione (ordine di implementazione)

1. Token + font in `globals.css`/`layout.tsx`; palette gruppi unificata in config.
2. Logo system in `public/brand/` + componente `Logo`; favicon/app icon.
3. Navigazione (Sidebar, MobileBottomNav) + command palette.
4. Home, poi risposta AI + citazioni (drawer), poi search/ranking/compass/timeline.
5. Landing, `?topic=` deep link, pagina metodologia, pass a11y/responsive.
