# Seconda prova sul Postgres v3 · 4/11/2026

35 domande nuove rispetto al pilota (`selezione.json`): 30 con risposta di riferimento in SQL (`benchmark/riferimento/`), scelte a giro fra le categorie, e 5 trappole (voto segreto sulla legge elettorale, Marco Meloni, Tabacci nel Misto senza componente, numero delle fiducie, salario minimo diventato delega). Servizio locale (http://localhost:8790), due domande alla volta, smistamento come il sito: le domande su posizioni dei gruppi al fascicolo, voti, date, numeri ed eventi di seduta all'agente. Giudizio come nel pilota: un giudice per domanda, ogni fatto confrontato col riferimento; nel secondo giro il giudice aveva accanto il giudizio del primo.

Il primo giro è in `giro1/`, il secondo nei file `<id>.json` di questa cartella; le risposte grezze in `raw/` e `giro1/raw/`.

## Numeri

| | Giro 1 | Giro 2 |
|---|---|---|
| Correttezza (0–2), 35 domande | 43 su 70, media 1,23 | **54 su 70, media 1,54** |
| Del tutto giuste (2) | 14 | 20 |
| Sbagliate o mancanti (0) | 6 | 1 (AULA-015) |
| Fonti ufficiali linkate | 8 risposte | 25 risposte |
| Trappole superate | 3 su 5 | 4 su 5 |
| Risposte vuote | 2 | 0 |

## Correzioni fra i due giri

- La risposta non si perde più se il controllo delle citazioni non finisce in tempo; il controllo usa l'indice di ricerca senza la posizione delle parole (0,6 s invece di oltre 8).
- Prompt: ogni fatto con il link ufficiale dei dati; le questioni di fiducia si contano per atto e data, non per votazione; le mozioni di sfiducia non sono fiducie.
- Dati: 4 mozioni di sfiducia individuale della Camera (art. 115, comma 3) non sono più segnate come fiducia.
- Strumenti: `conta_atti` filtra per ministero destinatario; `articolo` legge il testo di un articolo di una versione dell'atto.
- Sito: voti, date precise, applausi e «chi è intervenuto» vanno all'agente, non al fascicolo (le tre domande del fascicolo erano di questo tipo).

## Cosa resta (giro 2, domande sotto 2)

- **Ragionamento** (6): somma dei due rami (COMU-038, DJ-010), seduta tralasciata fra i risultati (DOC-019), totali mancanti (CIT-034), un audito mancante (COM-007), question time scambiato per la fine seduta (AULA-015).
- **Strumenti mancanti** (5): video degli interventi (APP-011), ore di seduta (GIO-009), emendamenti per articolo (COM-012), atti UE assegnati alle commissioni (COM-038), numeri d'atto delle leggi approvate (AULA-055).
- **Argomenti sbagliati** (3): firmatari invece del primo firmatario (GIO-049), temi troppo larghi (PARL-034), sintesi dell'articolo invece del testo (PARL-033).
- **Dati** (1): 1300 votazioni della Camera senza l'atto collegato, fra cui il voto finale della prima lettura della legge elettorale (AULA-034). Dopo il secondo giro la pipeline ricava l'atto dalla descrizione del voto («PDL 2822-A E ABB»); nel database locale 62 votazioni sono state collegate così.

## Costo

Circa 4 $ per i due giri. Il giro si è fermato una volta al tetto giornaliero della chat (10 $, raggiunto con le prove della giornata); per finire il secondo giro il tetto è stato alzato a 20 $ solo sul servizio locale.
