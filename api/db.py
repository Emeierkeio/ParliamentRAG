"""Connessione a Postgres con l'utente `lettura` (schema/lettura.sql): sola lettura e tempo massimo per query decisi dal
database, non dal codice. Segreti solo da ambiente o `.env`."""

from __future__ import annotations

from collections.abc import Iterator

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
