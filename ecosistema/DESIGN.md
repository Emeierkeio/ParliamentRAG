# Resoconto: design system della famiglia ParliamentRAG

Versione locale del nuovo ecosistema. Statico (HTML, CSS, JS senza build), si apre con
`python3 -m http.server 4873` dalla cartella `ecosistema/` e poi
`http://localhost:4873/`.

## Idea

Il resoconto stenografico ufficiale è la fonte di verità di tutta la famiglia, quindi
è anche il suo linguaggio visivo: carta e inchiostro, filetti sottili, numeri di sezione
in margine (`§ 1`), riferimenti in monospazio, e un segno di verifica accanto a ogni
citazione. ParliamentRAG definisce le **tre garanzie** (tutti i gruppi, voci autorevoli,
citazioni esatte); ogni sistema le applica e le mostra con lo stesso **sigillo**.

## Ecosistema

| Sito | Ruolo | Accento |
|---|---|---|
| ParliamentRAG (`parliamentrag/`) | Progetto di ricerca: metodo, dati, verifica | blu `#2d5f8f` |
| Stenografo (`stenografo/`) | Domande puntuali su sedute, atti, voti, con la fonte accanto a ogni frase | verde `#167a68` |
| Fascicoli (`fascicoli/`) | Un tema: posizione di ogni gruppo, voci autorevoli, citazioni esatte, voti collegati | verde |
| Scranno (`scranno/`) | L'Aula di Montecitorio seggio per seggio: chi siede dove, il suo lavoro, come ha votato | verde |

Collegamenti fissi: Stenografo → Fascicoli (domanda su un tema), Fascicoli → Scranno (un
voto si apre nell'Aula), Scranno → Stenografo (da un seggio chiedi cosa ha detto quel
deputato). Tutti leggono lo stesso grafo. Emendario, Arengo e Virgolettato **non si
nominano** finché non sono lanciati.

## File comuni

- `shared/famiglia.css`: token e componenti. Leggerlo prima di scrivere.
- `shared/famiglia.js`: inietta (niente barra di famiglia: tolta il 13/10) la testata
  `[data-testata]` e piede `[data-piede]`; gestisce tema, comparse `.compare`,
  pulsanti `[data-copia]`. Espone `window.MARCHI`, `window.ICONE`, `window.esc`,
  `window.numero`, `window.osservaComparse`, `window.FAMIGLIA`.
- `shared/data/dati.js` → `window.DATI`: numeri del grafo (`stats`) e il tema
  «Salario minimo» con 11 citazioni **verificate parola per parola sul resoconto** (una
  per gruppo + Governo, con `url` al resoconto) e il voto per gruppo
  sull'emendamento Conte del 5/12/2023.
- `shared/data/aula.js` → `window.AULA`: 664 seggi reali dell'Aula (coordinate
  `x`,`y` in viewBox 0 0 2560 1760, `k` tipo: d deputato, g governo, p presidenza,
  c comitato, a aggiuntivo), 399 deputati attuali con `id`, `n` nome, `g` sigla gruppo,
  `c` componente del Misto, e `v` = voto nella fiducia sulla legge elettorale del
  7/10/2026 (`favor`, `against`, `abstain`, `absent`, `n.d.` = voto non associato al
  seggio). Dati del voto in `AULA.vote`. Foto: `https://documenti.camera.it/_dati/leg19/schededeputatinuovosito/fotoDefinitivo/big/d{id}.jpg`.
- `parliamentrag/index.html`: la pagina di riferimento. Imitarne struttura e qualità.

## Scheletro di pagina

```html
<!doctype html>
<html lang="it" class="no-js" data-sito="stenografo" data-pagina="chiedi" data-prodotto="sistema">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Stenografo</title>
<link rel="icon" href="../shared/favicon-stenografo.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../shared/famiglia.css">
<style>/* solo stili della pagina, con i token */</style>
</head>
<body>
<a class="salta" href="#contenuto">Vai al contenuto</a>
<header data-testata></header>
<main id="contenuto">…</main>
<footer data-piede></footer>
<script src="../shared/data/dati.js"></script>   <!-- se serve -->
<script src="../shared/data/aula.js"></script>   <!-- se serve -->
<script src="../shared/famiglia.js"></script>
<script>/* logica della pagina */</script>
</body>
</html>
```

I sistemi mettono `data-prodotto="sistema"` (accento verde). ParliamentRAG non lo mette.

## Token (non inventare colori)

- Carta `--carta`, `--carta-2`, `--carta-3`, `--foglio`; inchiostro `--inchiostro` … `--inchiostro-4`;
  filetti `--filetto`, `--filetto-forte`.
- Accento `--accento`, `--accento-scuro`, `--accento-tenue` (cambiano da soli col prodotto).
- Voto: `--voto-si`, `--voto-no`, `--voto-ast`, `--voto-ass`. Stato: `--verificato`, `--errore`.
- **I gruppi non hanno colori.** Si scrivono per sigla (`.sigla`) o per esteso.
- Tipi: `--f-titolo` Newsreader (titoli, citazioni), `--f-testo` Geist (tutto il resto),
  `--f-mono` Geist Mono (etichette, id, numeri tecnici). Scala `--t-mega … --t-micro`.
- Spazi `--s-1 … --s-10` (base 4), raggi `--r-1 … --r-3`, `--r-pill`.
- Movimento: `--e-uscita`, `--e-std`, `--d-1 … --d-4`. Rispettare `prefers-reduced-motion`.
- Il tema scuro funziona già via token: non scrivere colori fissi nelle pagine.

## Componenti

`.pagina` (contenitore), `.sezione`, `.sezione-stretta`, `.testata` + `.testata__n`
(intestazione di sezione con `§ n`), `.titolo-mega/1/2/3`, `.titolo-4`, `.attacco`,
`.etichetta`, `.nota`, `.prosa`, `.collegamento`, `.btn` (`--accento`, `--linea`,
`--piccolo`, `--icona`), `.sigla`, `.foglio` (`--pad`, `.galleggia`), `.cit`
(`__testo`, `__fonte`, `__chi`, `--piccola`), `.bollino` (link «Resoconto» verificato),
`.fonte-in-linea` + `.rif` (frase con fonte), `.sigillo` (`__da`, `__voce`
con `data-esito="no"`), `.cifra` (`__n`, `__l`), `.tabella` in `.tabella-scorri`,
`.codice` + `.copia[data-copia=id]`, `.campo` (`--area`), `.spunta`, `.messaggio`
(`data-tipo`), `.schede` (bottoni con `aria-selected`), `.domanda` (details),
`.emiciclo` (cerchi con `data-v`), `.legenda`, `.compare` (+ `--ritardo`).

## Regole di contenuto

- Italiano, frasi brevi, niente gergo da marketing, niente emoji, niente punti
  esclamativi. Stile stop-slop: niente «non solo… ma», niente triadi decorative,
  niente «scopri», «potente», «rivoluzionario», «in un mondo in cui».
- Mai dati inventati. Usare `DATI` e `AULA`. Se serve un dato che non c'è, scrivere
  un segnaposto onesto («dato da collegare») o dire che è un esempio.
- Le risposte generate nei prototipi sono **esempi statici**: dirlo con un'etichetta
  discreta («Esempio · citazioni reali»). Le citazioni tra virgolette devono essere
  solo quelle di `DATI.tema.citazioni`, testuali.
- Authority: si dice «secondo i nostri criteri». Non mostrare punteggi numerici di
  autorevolezza: non li abbiamo calcolati qui.
- Gruppo Misto: attribuire alla componente (es. +Europa), mai al Misto monolitico.
- Progetto indipendente, non affiliato alla Camera.
- Link esterni con `rel="noopener"`.

## Qualità

- Responsive fino a 360px, nessuno scroll orizzontale del body.
- Stati: hover, focus visibile, attivo, disabilitato, vuoto, caricamento dove serve.
- Accessibilità: landmark, `aria-live` per i risultati, contrasto, target ≥ 40px.
- Non usare `scrollIntoView`. Nessuna libreria esterna salvo font Google.
