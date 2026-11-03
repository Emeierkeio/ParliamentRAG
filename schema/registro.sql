-- Registro delle chat, per trovare e correggere gli errori: domanda, risposta, strumenti, tempi e costo, senza indirizzo IP.
-- Sta in uno schema a parte: l'utente `lettura` dell'API e del server MCP non lo vede. Lo scrive l'utente `registro`,
-- che può solo inserire righe. Le righe si cancellano dopo il 31/12/2027 (registro dei trattamenti).
-- La password arriva come variabile psql (:'password') da .env (REGISTRO_PG_PASSWORD), mai negli argomenti dei comandi.
CREATE SCHEMA IF NOT EXISTS registro;

CREATE TABLE IF NOT EXISTS registro.chat (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  creata timestamptz NOT NULL DEFAULT now(),
  conversazione text,                              -- id casuale generato dal browser: tiene insieme i turni di una chat
  turno int,
  lingua text,
  domanda text NOT NULL,
  risposta text,
  strumenti jsonb,                                 -- [{nome, argomenti, risultati}] nell'ordine delle chiamate
  errore text,
  ms int,                                          -- dalla domanda all'ultima riga della risposta
  dollari numeric(10, 5),
  modello text
);
CREATE INDEX IF NOT EXISTS chat_creata ON registro.chat (creata);
CREATE INDEX IF NOT EXISTS chat_conversazione ON registro.chat (conversazione);

SELECT format('CREATE ROLE registro LOGIN PASSWORD %L', :'password') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'registro') \gexec
SELECT format('ALTER ROLE registro PASSWORD %L', :'password') \gexec
GRANT CONNECT ON DATABASE parliamentrag TO registro;
GRANT USAGE ON SCHEMA registro TO registro;
GRANT INSERT ON registro.chat TO registro;
REVOKE ALL ON SCHEMA registro FROM lettura;
ALTER ROLE registro SET statement_timeout = '5s';
ALTER ROLE registro CONNECTION LIMIT 10;
