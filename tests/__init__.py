def db_locale() -> bool:
    """Per i test che provano le funzioni SQL nel Postgres locale, in una transazione annullata."""
    from pipeline.carica.postgres import destinazione, prova
    try:
        prova()
        return destinazione() == "locale"
    except Exception:
        return False
