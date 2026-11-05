-- Dati che il sito scrive: le conversazioni condivise con un link e le traduzioni in inglese dei testi ufficiali.
-- Schema a parte, invisibile all'utente `lettura`. Lo scrive l'utente `sito`, che può solo leggere e inserire.
-- Le conversazioni condivise non hanno IP né altri dati di chi le crea: solo domande e risposte, come le vede chi apre il link.
-- La password arriva come variabile psql (:'password') da .env (SITO_PG_PASSWORD), mai negli argomenti dei comandi.
CREATE SCHEMA IF NOT EXISTS sito;

CREATE TABLE IF NOT EXISTS sito.condivisa (
  id text PRIMARY KEY,                             -- casuale, non indovinabile (secrets.token_urlsafe)
  creata timestamptz NOT NULL DEFAULT now(),
  conversazione jsonb NOT NULL                     -- {titolo, lingua, creata, turni: [{q, html}]}
);

CREATE TABLE IF NOT EXISTS sito.traduzione (
  testo text NOT NULL,
  lingua text NOT NULL,
  tradotto text NOT NULL,
  creata timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (lingua, testo)
);

-- limiti della chat: le domande dell'ora in corso per impronta dell'IP (mai l'IP; si cancellano allo scoccare dell'ora)
-- e la spesa di OpenAI, una riga per chiamata, sommata per giorno. In Postgres e non in un file del servizio, perché un
-- rilascio non li azzeri.
CREATE TABLE IF NOT EXISTS sito.domanda (impronta text NOT NULL, ts timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS domanda_impronta ON sito.domanda (impronta, ts);
CREATE TABLE IF NOT EXISTS sito.spesa (giorno date NOT NULL DEFAULT current_date, dollari numeric(12, 6) NOT NULL);
CREATE INDEX IF NOT EXISTS spesa_giorno ON sito.spesa (giorno);

-- statistiche di visita, fatte da noi: niente cookie e niente IP. `visitatore` è un'impronta di IP, browser e giorno con
-- una chiave segreta (LIMITE_SALE): conta i visitatori unici di un giorno e il giorno dopo non si ricollega a niente.
-- evento: pagina | domanda | fascicolo. Le righe si cancellano dopo 400 giorni.
CREATE TABLE IF NOT EXISTS sito.visita (
  ts timestamptz NOT NULL DEFAULT now(),
  giorno date NOT NULL DEFAULT current_date,
  evento text NOT NULL,
  percorso text,
  provenienza text,                                -- il dominio da cui si arriva, solo se esterno
  dispositivo text,                                -- telefono | tablet | computer, dalla larghezza della finestra
  browser text,
  lingua text,
  visitatore text NOT NULL
);
CREATE INDEX IF NOT EXISTS visita_giorno ON sito.visita (giorno);
-- paese (codice ISO) e regione, dall'IP con il file DB-IP in locale al momento della visita; l'IP non si salva
ALTER TABLE sito.visita ADD COLUMN IF NOT EXISTS paese text, ADD COLUMN IF NOT EXISTS regione text;
CREATE INDEX IF NOT EXISTS visita_ts ON sito.visita (ts);

SELECT format('CREATE ROLE sito LOGIN PASSWORD %L', :'password') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sito') \gexec
SELECT format('ALTER ROLE sito PASSWORD %L', :'password') \gexec
GRANT CONNECT ON DATABASE parliamentrag TO sito;
GRANT USAGE ON SCHEMA sito TO sito;
GRANT SELECT, INSERT ON sito.condivisa, sito.traduzione, sito.spesa TO sito;
GRANT SELECT, INSERT, DELETE ON sito.domanda TO sito;
GRANT SELECT, INSERT, DELETE ON sito.visita TO sito;
REVOKE ALL ON SCHEMA sito FROM lettura;
ALTER ROLE sito SET statement_timeout = '5s';
ALTER ROLE sito CONNECTION LIMIT 10;

-- per il pannello delle statistiche: quali strumenti usa la chat e cosa cerca, senza domande né risposte, solo dalle chat
-- del sito (le prove dell'API non hanno conversazione). Solo se lo schema del registro c'è (schema/registro.sql).
DO $$ BEGIN
  IF to_regclass('registro.chat') IS NOT NULL THEN
    CREATE OR REPLACE VIEW registro.uso_strumenti AS
      SELECT c.creata, s->>'nome' AS strumento,
             left(coalesce(s->'argomenti'->>'q', s->'argomenti'->>'testo'), 200) AS ricerca
      FROM registro.chat c, jsonb_array_elements(coalesce(c.strumenti, '[]'::jsonb)) s
      WHERE c.conversazione IS NOT NULL;
    -- tempi, costo ed esito di ogni domanda, senza domanda né risposta; turno vuoto = prova dell'API
    CREATE OR REPLACE VIEW registro.uso_chat AS
      SELECT creata, conversazione, turno, lingua, modello, dollari, ms, errore IS NOT NULL AS errore,
             left(errore, 200) AS errore_testo FROM registro.chat;   -- l'errore tecnico (eccezione, timeout), non la domanda
    -- i vettori della ricerca per significato: batch e token per giorno (vector_batch sta nello schema del v3)
    CREATE OR REPLACE VIEW registro.spesa_vettori AS
      SELECT (sent_at AT TIME ZONE 'Europe/Rome')::date AS giorno, count(*) AS batch, coalesce(sum(tokens), 0) AS token,
             count(*) FILTER (WHERE status <> 'completed') AS aperti
      FROM public.vector_batch GROUP BY 1;
    GRANT USAGE ON SCHEMA registro TO sito;
    GRANT SELECT ON registro.uso_strumenti, registro.uso_chat, registro.spesa_vettori TO sito;
  END IF;
END $$;
