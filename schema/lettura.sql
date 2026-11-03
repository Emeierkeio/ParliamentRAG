-- Utente di sola lettura per l'API: legge tutte le tabelle, non scrive niente, e ogni query ha un tempo massimo.
-- La password arriva come variabile psql (:'password') da .env (API_PG_PASSWORD), mai negli argomenti dei comandi.
SELECT format('CREATE ROLE lettura LOGIN PASSWORD %L', :'password') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lettura') \gexec
SELECT format('ALTER ROLE lettura PASSWORD %L', :'password') \gexec
GRANT CONNECT ON DATABASE parliamentrag TO lettura;
GRANT USAGE ON SCHEMA public TO lettura;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO lettura;
ALTER DEFAULT PRIVILEGES FOR ROLE parliamentrag IN SCHEMA public GRANT SELECT ON TABLES TO lettura;
ALTER ROLE lettura SET default_transaction_read_only = on;
ALTER ROLE lettura SET statement_timeout = '8s';
ALTER ROLE lettura CONNECTION LIMIT 20;
