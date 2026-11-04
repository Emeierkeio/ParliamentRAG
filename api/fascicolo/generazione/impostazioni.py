"""Modelli e parametri della generazione, gli stessi della configurazione del backend precedente (sezioni generation,
citation e retrieval.debate_relevance). Temperature e lunghezze massime restano nel codice di ogni passo, come prima."""

from __future__ import annotations

import re

# i modelli dei quattro passi; il chirurgo delle citazioni (passo 4) non usa modelli
MODELLI = {
    "analyst": "gpt-4.1-mini",          # passo 1: i claim della domanda
    "writer": "gpt-4.1",                # passo 2: una sezione per gruppo, con la citazione obbligatoria
    "integrator": "gpt-4.1",            # passo 3: solo l'introduzione (modo «assembler»)
    "quote_picker": "gpt-5.6-luna",     # la scelta della citazione: un indice fra candidati, poi verificato
}
MODELLO_VETTORI_PICCOLI = "text-embedding-3-small"   # coerenza introduzione-citazione e doppioni fra oratori

INTEGRATORE = "assembler"               # sezioni composte dal codice, il modello scrive solo l'introduzione
SCHEDA_POSIZIONE = {"enabled": True, "max_chunks": 5, "chars_per_chunk": 400, "context_chars": 500}
NESSUNA_EVIDENZA = "Nel corpus analizzato non risultano interventi rilevanti su questo tema."

FORMATO_CITAZIONE = "«{quote}» [{speaker}, {party}, {date}, ID:{id}]"
SOGLIA_DOPPIONI = 0.85                  # coseno oltre il quale due citazioni di oratori diversi sono la stessa
COERENZA_MINIMA = 0.22                  # calibrata sullo stile di gpt-4.1: le citazioni buone stanno fra 0,23 e 0,30
METODO_COERENZA = "embedding"

# gli id dei brani nel testo: «[CIT:b12]» durante la scrittura, «[«…»](b12)» alla fine. Corti, perché il modello li
# copia; il sito li legge con [\w.-]+.
ID_BRANO = r"b\d+"
RE_ID_BRANO = re.compile(ID_BRANO)
