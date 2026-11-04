# Seconda prova sul Postgres v3 · 4/11/2026

35 domande nuove rispetto al pilota (`selezione.json`): 30 con risposta di riferimento in SQL (`benchmark/riferimento/`), scelte a giro fra le categorie, e 5 trappole (voto segreto sulla legge elettorale, Marco Meloni, Tabacci nel Misto senza componente, numero delle fiducie, salario minimo diventato delega). Servizio locale (http://localhost:8790), due domande alla volta, smistamento come il sito: le domande su posizioni dei gruppi al fascicolo, voti, date, numeri ed eventi di seduta all'agente. Giudizio come nel pilota: un giudice per domanda, ogni fatto confrontato col riferimento; nel secondo giro il giudice aveva accanto il giudizio del primo.

Il primo giro è in `giro1/`, il secondo nei file `<id>.json` di questa cartella; le risposte grezze in `raw/` e `giro1/raw/`.

## Numeri

Il giro 3 rifà tutte le 35 domande dopo le correzioni del pomeriggio; il giro 4 rifà le 12 sotto 2 dopo altre correzioni, e il totale finale prende le altre 23 dal giro 3. I giudizi di ogni giro sono in `giro1/`, `giro2/`, `giro3/`; i file `<id>.json` di questa cartella sono l'ultimo giudizio di ogni domanda.

| | Giro 1 | Giro 2 | Giro 3 | Finale (giro 4 sulle 12) |
|---|---|---|---|---|
| Correttezza (0–2), 35 domande | 43 su 70 | 54 su 70 | 58 su 70 | **62 su 70, media 1,77** |
| Del tutto giuste (2) | 14 | 20 | 23 | 27 |
| Sbagliate o mancanti (0) | 6 | 1 | 0 | 0 |
| Trappole superate | 3 su 5 | 4 su 5 | 4 su 5 | 5 su 5 |
| Risposte vuote | 2 | 0 | 0 | 0 |

Le fonti dal giro 3 si contano con un metro più stretto (la scheda di un parlamentare non basta per un voto o un atto): 22 risposte su 35 linkano una fonte ufficiale che documenta il fatto.

## Le 8 domande ancora a 1

- APP-032: il «no» è giusto, ma non dice che il S. 1408 è in commissione.
- AULA-055: 22 approvazioni in sede legislativa su 23 (manca l'AC 2637 delle Commissioni VII e XII riunite).
- COM-007: 27 auditi, mancano i tre del 28/10, seduta con un titolo diverso.
- DOC-019: la seduta del 3/11 resta vaga (mancano DL 190 e DL 162).
- COMU-008: elenca 13 leggi ma scrive «12»; un link sbagliato.
- PARL-033: testo dell'articolo parafrasato e versione non dichiarata.
- COMU-038: la nota sul Misto contraddice la tabella; il riferimento usa una lista fissa di gruppi, il sistema i voti di fiducia.
- DJ-026: il question time resta senza numero (sono 6).

## Correzioni fra i giri 1 e 2

- La risposta non si perde più se il controllo delle citazioni non finisce in tempo; il controllo usa l'indice di ricerca senza la posizione delle parole (0,6 s invece di oltre 8).
- Prompt: ogni fatto con il link ufficiale dei dati; le questioni di fiducia si contano per atto e data, non per votazione; le mozioni di sfiducia non sono fiducie.
- Dati: 4 mozioni di sfiducia individuale della Camera (art. 115, comma 3) non sono più segnate come fiducia.
- Strumenti: `conta_atti` filtra per ministero destinatario; `articolo` legge il testo di un articolo di una versione dell'atto.
- Sito: voti, date precise, applausi e «chi è intervenuto» vanno all'agente, non al fascicolo (le tre domande del fascicolo erano di questo tipo).

## Cosa restava dopo il giro 2

- **Ragionamento** (6): somma dei due rami (COMU-038, DJ-010), seduta tralasciata fra i risultati (DOC-019), totali mancanti (CIT-034), un audito mancante (COM-007), question time scambiato per la fine seduta (AULA-015).
- **Strumenti mancanti** (5): video degli interventi (APP-011), ore di seduta (GIO-009), emendamenti per articolo (COM-012), atti UE assegnati alle commissioni (COM-038), numeri d'atto delle leggi approvate (AULA-055).
- **Argomenti sbagliati** (3): firmatari invece del primo firmatario (GIO-049), temi troppo larghi (PARL-034), sintesi dell'articolo invece del testo (PARL-033).
- **Dati** (1): 1300 votazioni della Camera senza l'atto collegato, fra cui il voto finale della prima lettura della legge elettorale (AULA-034). Dopo il secondo giro la pipeline ricava l'atto dalla descrizione del voto («PDL 2822-A E ABB»); nel database locale 62 votazioni sono state collegate così.

## Costo

Circa 4 $ per i due giri. Il giro si è fermato una volta al tetto giornaliero della chat (10 $, raggiunto con le prove della giornata); per finire il secondo giro il tetto è stato alzato a 20 $ solo sul servizio locale.

## Correzioni fra i giri 2 e 4

- Strumenti nuovi: argomenti delle sedute per organo, sede e fase (fine seduta, sede legislativa, atti UE); conteggio delle sedute con le ore dai video; video WebTV e link al resoconto negli interventi; emendamenti per articolo, tipo e gruppo del primo firmatario; atti per tema dei thesauri; maggioranza e opposizione negli interventi; testo di un articolo anche dentro una legge di conversione; link al resoconto di ogni seduta.
- Conteggio delle fiducie: esclusa la fiducia iniziale al Governo (Camera 70, Senato 57).
- Prompt: rami mai sommati, niente somme a mano, totale prima delle parti, «questa settimana» nel calendario, versione dell'articolo dichiarata, emendamenti per primo firmatario.
- Dati: 1082 votazioni della Camera in più legate all'atto (restano 156, quasi tutte su documenti che non sono in `act`); 46 membri del governo con il nome; 7 testi a fronte con la reiezione divisi in articoli.
