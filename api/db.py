"""Connessione a Postgres con l'utente `lettura` (schema/lettura.sql): la sola lettura e il tempo massimo per query li
impone il database. Segreti solo da ambiente o `.env`."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from pipeline.ambiente import env


def connessione() -> psycopg.Connection:
    return psycopg.connect(host=env("API_PG_HOST", "localhost"), port=int(env("PG_PORTA", "5440")), dbname="parliamentrag",
                           user=env("API_PG_UTENTE", "lettura"), password=env("API_PG_PASSWORD"), row_factory=dict_row,
                           application_name="parliamentrag-api", autocommit=True)


def per_richiesta() -> Iterator[psycopg.Connection]:
    """Dipendenza FastAPI: una connessione per richiesta, chiusa alla fine."""
    with connessione() as c:
        yield c


@contextmanager
def connessione_sito() -> Iterator[psycopg.Connection | None]:
    """Connessione dell'utente `sito` (schema/sito.sql), che scrive nello schema `sito`; None se non è configurato
    (SITO_PG_PASSWORD) o non risponde."""
    try:
        password = env("SITO_PG_PASSWORD")
    except KeyError:
        yield None
        return
    try:
        c = psycopg.connect(host=env("API_PG_HOST", "localhost"), port=int(env("PG_PORTA", "5440")), dbname="parliamentrag",
                            user="sito", password=password, row_factory=dict_row, application_name="parliamentrag-sito",
                            autocommit=True, connect_timeout=5)
    except psycopg.Error as e:
        logging.getLogger("parliamentrag.db").warning("schema del sito non raggiungibile: %s", type(e).__name__)
        yield None
        return
    with c:
        yield c
