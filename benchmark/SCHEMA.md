# Benchmark delle domande sul Parlamento: formato

Una domanda per riga in JSONL (`parti/<profilo>.jsonl`, poi riunite in `domande.jsonl`).

| Campo | Valori | Cosa dice |
|---|---|---|
| `id` | `LEG-001` … | prefisso del profilo e numero |
| `profilo` | servizio_legislativo, funzionario_commissione, comunicazione, giornalista, aula, parlamentare_staff, lobbista, terzo_settore, cittadino, appassionato, studente, docente, ricercatore, data_journalist, pubblica_amministrazione | chi la fa |
| `domanda` | testo | come la scriverebbe quella persona, in italiano |
| `categoria` | iter, voti, persone, gruppi, interventi, emendamenti, sindacato_ispettivo, commissioni, audizioni, governo, calendario, temi, confronto, statistiche, testi, video, reazioni, regolamento, fonti | l'area del dominio |
| `tipo_risposta` | fatto, elenco, conteggio, classifica, linea_del_tempo, confronto_gruppi, sintesi_con_citazioni, testo, link | la forma della risposta attesa |
| `ramo` | camera, senato, entrambi | |
| `legislatura` | 19, 18, piu_legislature | |
| `dati_v3` | elenco di tabelle di `schema/v3.sql` | cosa serve per rispondere |
| `copertura` | si, parziale, no | se i dati v3 di oggi bastano |
| `manca` | testo o null | cosa manca quando la copertura non è piena |
| `garanzie` | sottoinsieme di tutti_i_gruppi, voci_autorevoli, citazioni_esatte | le garanzie che la risposta deve rispettare |
| `verifica` | esatta, giudizio | esatta: la risposta giusta si calcola dai dati (SQL); giudizio: serve una valutazione |
| `difficolta` | facile, media, difficile | |
| `note` | testo o null | trappole, ambiguità, cosa deve fare il sistema |
