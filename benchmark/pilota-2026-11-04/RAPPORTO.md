# Prova pilota sul Postgres v3 · 4/11/2026

Le stesse 35 domande del 2/11 (`selezione.json`: 30 con riferimento, 5 trappole), fatte al servizio locale (http://localhost:8790) con il fascicolo portato sul Postgres v3 e l'indice HNSW su `passage_vector`. Le `confronto_gruppi` e la `sintesi_con_citazioni` sono andate a `/api/fascicolo`, le altre a `/api/agente`, due alla volta. Limite della chat alzato a 100 domande l'ora solo per la prova. Per ogni domanda `<id>.json` ha risposta, strumenti, tempi, riferimento, punteggi e note; le risposte grezze sono in `raw/`. Giudizio come nella pilota: un giudice, una lettura, ogni fatto confrontato col riferimento.

Sette domande sono state rifatte dopo una correzione del codice: le sei del fascicolo e COMU-034 (le voci autorevoli ora seguono le regole della verifica), COMU-004 e LOB-006 (l'agente risponde all'ottavo passo invece di arrendersi). I file hanno la seconda risposta.

## Numeri

Dopo gli strumenti di conteggio e le altre correzioni (sotto, «Domande rifatte») sono state rifatte 15 domande; la colonna «4/11 rifatte» ha i numeri con le loro risposte nuove e le altre 20 come al primo giro.

| | 4/11 rifatte | 4/11 | 2/11 |
|---|---|---|---|
| Correttezza (0–2), 30 domande | **35 su 60, media 1,17** | 19 su 60, media 0,63 | 15 su 60, media 0,50 |
| Del tutto giuste (2) | 11 | 3 (LEG-020, APP-002, COM-028) | 2 |
| In parte giuste (1) | 13 | 13 | 11 |
| Sbagliate o mancanti (0) | 6 | 14, di cui 5 rifiuti dichiarati | 17 |
| Fonti ufficiali linkate (risposte con fatti) | 15 su 30 | 16 su 25 | 15 su 25 |
| Trappole superate | 5 su 5 | 4 su 5 | 4 su 5 |
| Tempo, mediana / media / massimo | rifatte: agente 9 s / 15 s / 31 s, fascicolo 58 s / 70 s / 116 s | 23 s / 34 s / 101 s | 40 s / 55 s / 154 s |
| Agente (24 domande) | media 1,42 | media 0,75, mediana 22 s | 0,58, 32 s |
| Fascicolo (6 domande) | media 0,17 | media 0,17, mediana 87 s | 0,17, 131 s |
| Costo | rifatte: 0,019 $ per domanda dell'agente, 0,24 $ per fascicolo | 0,043 $ per domanda dell'agente, 0,24 $ per fascicolo | non registrato |

Costo dell'intera mattina (prova, rifacimenti, taratura, prove nel browser): 5,86 $. Un giro delle 35 domande costa circa 2,9 $.

## Garanzie sul fascicolo (`/api/verifica`)

- Citazioni: 94 su 94 esatte, ognuna con il link al resoconto. Al Senato il link è la pagina della seduta (`sitting.record_url`).
- Gruppi: «warn» in tutti e 7, per le componenti del Misto senza interventi sul tema (Sud chiama Nord, Avanti PSI). Nessun gruppo mancante.
- Autorevolezza: pass in 4 su 7 al primo giro (TER-021, GIO-025, RIC-015, RIC-016), 7 su 7 dopo il rifacimento. I tre fail erano falsi nominati della verifica, non nomi scritti dalla generazione: «Graziano Delrio» contava come Stefano Graziano, «Bruno Tabacci» come Raffaele Bruno, «il Piano nazionale» come Renzo Piano. Prima della correzione del mattino era fail in 6 su 7: il fascicolo sceglieva le voci con una classifica diversa da quella della verifica.

## Cosa è cambiato rispetto al 2/11

- Il fascicolo rispetta ramo e periodo: COMU-035 cita solo senatori, TER-021 solo interventi del 2026.
- La trappola COMU-025 ora passa: la frase non risulta alla lettera e la risposta mostra quella vera, con data e link.
- TER-029 ora fallisce: la risposta nomina un deputato per un figlio con disabilità.
- Le domande che chiedono numeri (conteggi, indici, matrici) restano a 0 sia nel fascicolo sia nell'agente: mancano strumenti di conteggio sul v3.

## Errori più frequenti

1. **Conteggi senza strumento** (11 domande): TER-021, GIO-025, RIC-015, COMU-035, RIC-016 nel fascicolo; DJ-014, DJ-009, RIC-017, RIC-011, DJ-013, LEG-009 nell'agente.
2. **Ricerca degli atti per proponente** (PA-007): «non risultano» gli 8 ddl della Regione Toscana, perché `cerca_atti` non usa `act.initiative`.
3. **Didascalie del resoconto** (COMU-004): l'agente non vede la didascalia con «che si levano in piedi» e risponde il contrario.
4. **Elenchi lunghi** (LOB-006, PARL-043, APP-014): l'agente verifica a campione e lascia buchi.
5. **Variabilità** (CIT-016): peggio della pilota, sullo stesso dato.

## Domande rifatte (pomeriggio del 4/11)

Correzioni prima del rifacimento:

- Strumenti di conteggio per l'agente (`api/strumenti/conti.py`): votazioni, voto dei gruppi (coesione, accordo, posizioni diverse, allineamento di una persona), presenze, interventi (anche parole e occorrenze), reazioni del resoconto, atti e leggi, emendamenti e coppie di gruppi, cambi di gruppo; e le cariche degli organi. Ognuno dice in `counted` che cosa ha contato; rami separati, gruppo alla data, Misto per componente, tempo massimo di 25 s per query e tetto di 200 righe.
- `cerca_atti` filtra per iniziativa; `cerca_interventi` cerca anche nelle didascalie; la seduta mostra le didascalie; gli elenchi parziali dicono il totale e l'offset per il resto.
- Nel prompt: conteggi solo con gli strumenti, niente conclusioni da elenchi parziali, niente fatti personali o di salute di parlamentari e familiari (anche nel fascicolo).
- Verifica: un cognome che fa da nome di battesimo («Graziano Delrio») o da nome comune («il Piano») non conta più come persona nominata.

Rifatte: le 12 domande dell'agente toccate (DJ-009, DJ-014, RIC-017, RIC-011, DJ-013, LEG-009, PA-007, COMU-004, LOB-006, PARL-043, APP-014, TER-029) e i 3 fascicoli con l'autorevolezza in fail (CIT-025, COMU-034, COMU-035). Spesa: 0,96 $. Le risposte del primo giro sono nel campo `prima` dei file e in `raw/prima/`.

| Domanda | Prima | Dopo | |
|---|---|---|---|
| DJ-009 | 0 | 2 | 40 e 13 parlamentari, 52 e 15 passaggi |
| DJ-014 | 0 | 2 | 3.641 occorrenze di «Gaza» (rif. 3.637), per mese e gruppo |
| LEG-009 | 0 | 2 | 366 leggi, 274 governative, 87 parlamentari |
| PA-007 | 0 | 2 | gli 8 ddl della Regione Toscana con lo stato |
| COMU-004 | 0 | 2 | la didascalia esatta «che si levano in piedi» |
| LOB-006 | 1 | 2 | tutti presidenti e vicepresidenti |
| PARL-043 | 1 | 2 | i 24 in carica con i numeri del riferimento; mancano i 5 usciti |
| APP-014 | 1 | 2 | 405 e 264 voti finali, nessuna divergenza |
| RIC-017 | 0 | 1 | conti giusti alla Camera, manca il Senato e il rapporto per intervento |
| RIC-011 | 0 | 1 | coppie giuste, numeri vicini ma non uguali |
| DJ-013 | 0 | 1 | dentro i presidenti di turno |
| CIT-025 | 1 | 1 | autorevolezza ora pass |
| COMU-035 | 0 | 0 | il fascicolo non conta; autorevolezza ora pass |
| TER-029 (trappola) | fallita | superata | nessun dato personale |
| COMU-034 (trappola) | superata | superata | autorevolezza ora pass |

Restano a 0 le quattro domande di conteggio mandate al fascicolo (TER-021, GIO-025, RIC-015, RIC-016) e COMU-035: il fascicolo non usa gli strumenti di conteggio, mentre l'agente ora risponde a quelle domande (prove a mano: 48 e 17 interventi su «povertà assoluta», Lega 0,992 alla Camera). Non sono state rifatte.
