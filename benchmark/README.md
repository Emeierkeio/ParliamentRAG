# Benchmark delle domande sul Parlamento

658 domande su Camera e Senato come le farebbero persone di 15 profili, scritte il 2/11/2026 da sei agenti che impersonavano ciascun profilo. Gli agenti hanno letto il database v3 in sola lettura, quindi atti, persone, sedute e numeri sono veri. Il formato dei campi è in [SCHEMA.md](SCHEMA.md); le domande sono in `domande.jsonl` e le parti di partenza in `parti/`.

Non sono ancora validate da esperti. Per 100 domande c'è una risposta di riferimento calcolata in SQL (sotto).

## Quanto copre il v3 oggi

| | Domande | Sì | In parte | No |
|---|---|---|---|---|
| Totale | 658 | 296 (45%) | 275 (42%) | 87 (13%) |

507 domande hanno una risposta giusta calcolabile dai dati (`verifica: esatta`), 151 chiedono un giudizio. 633 riguardano la XIX, 7 la XVIII, 18 più legislature.

Il 2/11/2026, dopo le risposte di riferimento, sono cambiate le etichette di 19 domande (10 da «in parte» a «sì», 5 da «sì» a «in parte», 3 da «in parte» a «no», 1 da «sì» a «no») e le note o il campo `manca` di altre 7. Prima erano 292 sì, 283 in parte, 83 no.

### Per profilo

| Profilo | Domande | Sì | In parte | No |
|---|---|---|---|---|
| servizio_legislativo | 58 | 24 | 30 | 4 |
| funzionario_commissione | 47 | 15 | 24 | 8 |
| comunicazione | 53 | 27 | 21 | 5 |
| giornalista | 53 | 22 | 24 | 7 |
| aula | 58 | 29 | 20 | 9 |
| parlamentare_staff | 56 | 30 | 17 | 9 |
| lobbista | 60 | 29 | 23 | 8 |
| terzo_settore | 45 | 15 | 25 | 5 |
| cittadino | 36 | 18 | 13 | 5 |
| appassionato | 36 | 23 | 10 | 3 |
| studente | 25 | 12 | 11 | 2 |
| docente | 21 | 9 | 10 | 2 |
| ricercatore | 48 | 16 | 22 | 10 |
| data_journalist | 31 | 15 | 13 | 3 |
| pubblica_amministrazione | 31 | 12 | 12 | 7 |

### Per categoria

| Categoria | Domande | Sì | In parte | No |
|---|---|---|---|---|
| voti | 72 | 50 | 18 | 4 |
| persone | 60 | 28 | 19 | 13 |
| iter | 57 | 30 | 22 | 5 |
| commissioni | 47 | 14 | 31 | 2 |
| statistiche | 46 | 29 | 15 | 2 |
| emendamenti | 45 | 17 | 21 | 7 |
| interventi | 41 | 25 | 15 | 1 |
| sindacato_ispettivo | 38 | 18 | 16 | 4 |
| audizioni | 36 | 11 | 23 | 2 |
| governo | 28 | 11 | 12 | 5 |
| gruppi | 28 | 20 | 5 | 3 |
| fonti | 27 | 14 | 7 | 6 |
| regolamento | 23 | 0 | 14 | 9 |
| temi | 20 | 3 | 16 | 1 |
| calendario | 19 | 4 | 8 | 7 |
| confronto | 19 | 2 | 7 | 10 |
| testi | 19 | 5 | 14 | 0 |
| reazioni | 17 | 8 | 8 | 1 |
| video | 16 | 7 | 4 | 5 |

## Cosa manca, per domande sbloccate

Stima per parole chiave sul campo `manca`, fatta sulla prima versione: 366 domande non coperte del tutto, oggi 362 (una domanda può contare in più righe; 117 non rientrano in nessun gruppo). Due righe sono in parte superate: i temi EuroVoc ora hanno il nome (`concept` è caricata) e al Senato quasi tutti i voti finali e sugli articoli sono legati all'atto. Il campo `manca` di altre 20 domande, non ancora ricontrollate, cita i temi EuroVoc (14) o `vote_act` (6) e va riletto alla luce di questi caricamenti.

| Lavoro | Domande |
|---|---|
| Audizioni e memorie del Senato, testo delle memorie (solo 1.352 su 6.663 alla Camera) | 29 |
| Risposte del governo alle interrogazioni, esito di interrogazioni e ordini del giorno | 28 |
| XVIII e legislature precedenti | 24 |
| Regolamenti parlamentari e precedenti | 23 |
| Atti del governo (AG) come atti, atti UE, petizioni | 22 |
| Autorevolezza e ricerca semantica | 21 |
| Senato: assenti nei voti, presidente di turno, Misto per componente | 18 |
| Testo vigente (Normattiva) e decreti attuativi | 18 |
| Nomi dei temi (EuroVoc, TESEO) | 16 |
| Senato: voti legati agli atti | 15 |
| Esiti degli emendamenti | 14 |
| Senato: iter (assegnazioni, relatori, abbinamenti, fasi) | 13 |
| Calendario e sedute future di Senato e commissioni | 12 |
| Video di Senato e commissioni | 12 |
| Trattamento economico, collegi, contatti, bilanci | 11 |
| Reazioni: gruppo di chi reagisce | 7 |

## Problemi nei dati trovati scrivendo le domande

- Al Senato 2.546 righe di `vote_act` su 12.877 non hanno l'atto: tutte le 58 fiducie, le mozioni, le risoluzioni e gli ordini del giorno. I voti finali e sugli articoli sono quasi tutti legati (all'inizio non lo era nessuno).
- Al Senato i voti individuali non hanno righe per gli assenti.
- 217.598 emendamenti su 229.617 non hanno l'esito; al Senato nessuno.
- La XIII commissione della Camera aveva due presidenze aperte (Carloni senza data di fine, Bruzzone dal 13/10/2026): erano righe doppie di `office`, corrette il 2/11/2026.
- `act.status` è vuoto per le 13.007 interrogazioni a risposta scritta.
- `concept` era vuota: i temi EuroVoc sono entrati con il caricamento del 2/11/2026 (21.373 concetti).
- In alcuni voti di fiducia sulla legge elettorale il gruppo del votante non è risolto.

## Risposte di riferimento

In `riferimento/<id>.json` c'è la risposta giusta di 100 domande: le query SQL, il risultato, la risposta in italiano, lo stato, i limiti e i problemi nei dati trovati. Le domande sono state estratte a caso (seed 19), stratificate per categoria, fra quelle con `verifica: esatta` e copertura «sì» o «in parte» (le etichette di allora: 58 sì e 42 in parte). I quattro lotti di partenza sono in `riferimento/lotto1.jsonl` … `lotto4.jsonl`.

| Stato | Risposte |
|---|---|
| calcolata | 65 |
| parziale | 31 |
| non_calcolabile | 4 |

Le query girano su Postgres v3 (`docker compose exec testi psql`, in sola lettura). Dopo ogni ricaricamento dei dati vanno ricalcolate: `python3 benchmark/riferimento/ricalcola.py` dalla cartella `piattaforma` riesegue tutte le query e dice quali risultati sono cambiati; con `--scrivi` aggiorna `risultato`, e risposta, stato e limiti vanno riletti a mano. Le 25 risposte toccate dalle correzioni di `vote_act` e `office` sono state ricalcolate il 2/11/2026.

## Problemi nei dati trovati dalle risposte di riferimento

Il dettaglio, con la query che li mostra, è nel campo `problemi_dati` di ogni risposta.

**Voti**
- Corretto il 2/11/2026: 6.046 righe di `vote_act` della Camera con riferimento `ac19_N` puntavano al ddl del Senato con lo stesso numero (`it:senato:19:ddl:N`). Ora puntano all'atto della Camera.
- Dal giugno 2026 949 voti della Camera non hanno `vote_act`, contro 9 nei cinque mesi prima; molti hanno titolo «Votazione» o «Votazione finale» e l'atto solo in `description` (es. il voto finale della legge elettorale in prima lettura).
- Al Senato le 58 fiducie non hanno `vote_act`: l'atto si legge dal titolo del voto.
- Al Senato le schede non hanno righe per gli assenti, e i «presenti non votanti» delle schede non tornano con `present - voting` in 7.794 voti palesi su 8.397. `vote.source_url` e `vote.presided_by` sono vuoti.
- `vote.kind = 'final'` su 117 voti della Camera che non sono finali. Entità HTML codificate due volte in 1.604 testi di voto.
- 545 schede della Camera hanno il gruppo segnaposto `gr9999`; 129 hanno un gruppo diverso da `membership` alla data.

**Atti e iter**
- Al Senato `act_step`, `act_assignment` e `act_rapporteur` non hanno righe e `status_date` è vuota: l'iter si ricava dalle sedute.
- S. 1353 e 1353-B hanno `law_number` 690 e `law_date` 2100-01-01 (segnaposto). La stessa legge ha `law_date` diverse nei due rami (L. 162/2025, L. 11/2026). Leggi ordinarie e costituzionali condividono il numero.
- Al Senato `initiative` è testo libero («Popolare» e «POPOLARE», «CNEL» e «C.N.E.L.»).
- `act.status` è vuoto per tutti gli atti di indirizzo e sindacato ispettivo; i titoli delle interrogazioni scritte non hanno l'oggetto.
- Trasmissioni copiate su C. X e C. X-B (37 righe doppie). Marcatori HTML (`<em>`) nei titoli della Camera.
- I progetti di legge non hanno temi in `act_subject`; 493 righe puntano a concetti assenti da `concept`. Il descrittore «denominazione di origine» compare in 178 interrogazioni al Ministero del Lavoro dove non c'entra.
- Atti del Governo e Doc. non esistono come atti: i loro riferimenti in `agenda_item_act` restano senza atto.

**Persone, gruppi e cariche**
- Corretto il 2/11/2026: 272 righe aperte di `office` duplicavano una riga chiusa (stessa persona, organo, carica e data d'inizio). Restano tre comitati della III Commissione con due presidenze aperte della stessa persona (dal 18/9/2025 e dal 1/10/2025).
- Al Senato il Misto non è diviso per componente, i gruppi non hanno date e `act_sponsor` usa gli id della Camera (serve `person_same_as`). `office` non ha la Presidenza del Senato.
- Le appartenenze si sovrappongono nel giorno del passaggio (`end_date` inclusa). `mandate` non ha un campo comune per il tipo di elezione.
- `body.name` delle commissioni permanenti della Camera è solo il numero («X Commissione»).

**Interventi e reazioni**
- Alla Camera `speech.as_group` di Noi Moderati è troncato («NM(N-C-U-I») e il resto finisce nel testo; al Senato `as_group` contiene didascalie e orari. Il parsing si sta correggendo: le risposte che usano `as_group` vanno ricontrollate dopo il ricaricamento degli interventi.
- Alla Camera `as_office` è vuoto per i membri del governo: la carica resta all'inizio del testo (9.730 interventi).
- Al Senato le reazioni non dicono chi reagisce (`reaction_from` senza righe del Senato). Didascalie delle reazioni rimaste nel testo di 8.586 interventi.

**Commissioni, sedute e documenti**
- Il Bollettino delle commissioni della Camera parte dal 15/5/2023. Al Senato mancano molte sedute di commissione del 2026 (la 5ª ne ha 12 caricate su circa 70).
- Una sola seduta in programma in tutto il database (Aula, 3/11/2026). `sitting.provisional` vale sempre false per il Bollettino.
- Le audizioni delle indagini conoscitive compaiono due volte (Bollettino e stenografico); `sitting.seat` ha varianti per la stessa sede.
- `document.author_raw` non è normalizzato («Confindustria» e «CONFINDUSTRIA»). 1.322 dossier su 2.353 hanno caratteri rotti; 1.884 non hanno atti collegati.

**Emendamenti**
- Al Senato nessun emendamento ha l'esito; alla Camera lo stesso emendamento compare in più righe e nessuno risulta «respinto».

## Trappole incluse

Voti segreti (si sa chi ha partecipato, non come ha votato), missioni che non sono assenze, deputati dimessi o subentrati, omonimi (Marco Meloni e la Presidente del Consiglio), AC e AS con lo stesso numero, una fiducia con più votazioni, il salario minimo diventato una delega, domande di parte, richieste di opinione, citazioni inventate, profilazione oltre il ruolo pubblico, domande fuori dominio.
