-- Schema v3 in Postgres: una tabella per etichetta, colonne per le relazioni uno-a-molti,
-- tabelle di collegamento per le molti-a-molti. Le chiavi sono gli uri dello schema v3.
-- Si applica a ogni giro (IF NOT EXISTS); le modifiche incompatibili vanno in schema/migrazioni/.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sitting (
  uri text PRIMARY KEY,
  chamber text NOT NULL,              -- camera | senato | (consigli: it-25:consiglio …)
  body text NOT NULL,                 -- organo: aula o commissione
  number int NOT NULL,
  date date NOT NULL,
  status text NOT NULL DEFAULT 'held',   -- planned | held
  source text NOT NULL,
  source_key text,
  source_hash text,
  loaded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sitting_date ON sitting (chamber, date);
-- sedute di commissione dal Bollettino (resoconto sommario): sede, chi presiede, orari, governo presente
ALTER TABLE sitting ADD COLUMN IF NOT EXISTS kind text;              -- assembly_verbatim | committee_summary
ALTER TABLE sitting ADD COLUMN IF NOT EXISTS body_code text;         -- codice della commissione nel Bollettino (01, 0109 …)
ALTER TABLE sitting ADD COLUMN IF NOT EXISTS body_name text;
ALTER TABLE sitting ADD COLUMN IF NOT EXISTS seat text;              -- SEDE REFERENTE, SEDE CONSULTIVA, AUDIZIONI …
ALTER TABLE sitting ADD COLUMN IF NOT EXISTS bulletin_number int;
ALTER TABLE sitting ADD COLUMN IF NOT EXISTS provisional boolean;
ALTER TABLE sitting ADD COLUMN IF NOT EXISTS presidency text;
ALTER TABLE sitting ADD COLUMN IF NOT EXISTS presided_by text;
ALTER TABLE sitting ADD COLUMN IF NOT EXISTS government_present text;
ALTER TABLE sitting ADD COLUMN IF NOT EXISTS start_time text;
ALTER TABLE sitting ADD COLUMN IF NOT EXISTS end_time text;
CREATE INDEX IF NOT EXISTS sitting_body ON sitting (body, date);

CREATE TABLE IF NOT EXISTS agenda_item (
  uri text PRIMARY KEY,
  sitting text NOT NULL REFERENCES sitting (uri) ON DELETE CASCADE,
  ord int NOT NULL,
  title text,
  procedural boolean
);

CREATE TABLE IF NOT EXISTS agenda_item_act (      -- ABOUT: atti discussi, per ora come riferimento della fonte (pdl:2822-B)
  item text NOT NULL REFERENCES agenda_item (uri) ON DELETE CASCADE,
  act_ref text NOT NULL,
  act text,                                        -- uri dell'atto, quando il connettore degli atti lo risolve
  PRIMARY KEY (item, act_ref)
);

CREATE TABLE IF NOT EXISTS person (                -- una persona per tutte le legislature; segnaposto (stub) finché l'anagrafica non la completa
  uri text PRIMARY KEY,
  stub boolean NOT NULL DEFAULT true,
  given_name text, family_name text, sort_name text, birth_date date, qid text
);
ALTER TABLE person ADD COLUMN IF NOT EXISTS camera_id text;
ALTER TABLE person ADD COLUMN IF NOT EXISTS gender text;
ALTER TABLE person ADD COLUMN IF NOT EXISTS birth_place text;
ALTER TABLE person ADD COLUMN IF NOT EXISTS photo text;
ALTER TABLE person ADD COLUMN IF NOT EXISTS education text;
ALTER TABLE person ADD COLUMN IF NOT EXISTS profession text;
ALTER TABLE person ADD COLUMN IF NOT EXISTS source text;
ALTER TABLE person ADD COLUMN IF NOT EXISTS source_uri text;
ALTER TABLE person ADD COLUMN IF NOT EXISTS senato_id text;

-- gruppi e componenti del Misto (kind = misto_component, part_of = il Misto)
CREATE TABLE IF NOT EXISTS grp (
  uri text PRIMARY KEY,
  chamber text NOT NULL, legislature int NOT NULL,
  kind text NOT NULL,                              -- group | misto_component
  name text NOT NULL, short_name text,
  start_date date, end_date date,
  part_of text REFERENCES grp (uri) DEFERRABLE INITIALLY DEFERRED,
  source text NOT NULL, source_uri text
);

-- organi: commissioni, giunte, comitati, delegazioni, presidenza
CREATE TABLE IF NOT EXISTS body (
  uri text PRIMARY KEY,
  chamber text NOT NULL, legislature int NOT NULL,
  kind text NOT NULL, kind_raw text,
  name text NOT NULL,
  start_date date, end_date date,
  part_of text,
  source text NOT NULL, source_uri text
);

-- relazioni datate (SCHEMA-V3 §2 e §4): end_date assente = in corso, ultimo giorno incluso
CREATE TABLE IF NOT EXISTS mandate (               -- MANDATE
  person text NOT NULL REFERENCES person (uri),
  chamber text NOT NULL, legislature int NOT NULL,
  start_date date NOT NULL, end_date date, end_reason text, validated date,
  constituency text, college text, system text, list text,
  source_uri text,
  PRIMARY KEY (person, chamber, legislature, start_date)
);
ALTER TABLE mandate ADD COLUMN IF NOT EXISTS kind text;            -- elected | life | ex_officio
ALTER TABLE grp ADD COLUMN IF NOT EXISTS aliases text[];            -- altri nomi del gruppo nella legislatura (Senato)

CREATE TABLE IF NOT EXISTS membership (            -- MEMBER_OF: gruppi e componenti del Misto
  person text NOT NULL REFERENCES person (uri),
  grp text NOT NULL REFERENCES grp (uri) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'member',
  start_date date, end_date date, end_reason text
);
CREATE INDEX IF NOT EXISTS membership_person ON membership (person);
CREATE TABLE IF NOT EXISTS seat (                  -- SITS_ON: appartenenza agli organi
  person text NOT NULL REFERENCES person (uri),
  body text NOT NULL REFERENCES body (uri) ON DELETE CASCADE,
  role text NOT NULL, role_raw text,
  start_date date NOT NULL, end_date date, end_reason text
);
CREATE INDEX IF NOT EXISTS seat_person ON seat (person);
CREATE TABLE IF NOT EXISTS office (                -- OFFICE: cariche negli organi e nei gruppi
  person text NOT NULL REFERENCES person (uri),
  target text NOT NULL,                            -- uri di un body o di un grp
  title text NOT NULL, title_raw text,
  start_date date NOT NULL, end_date date
);
CREATE INDEX IF NOT EXISTS office_person ON office (person);

ALTER TABLE office ADD COLUMN IF NOT EXISTS end_reason text;
ALTER TABLE office ADD COLUMN IF NOT EXISTS interim boolean;
ALTER TABLE office ADD COLUMN IF NOT EXISTS note text;
ALTER TABLE office ADD COLUMN IF NOT EXISTS source_uri text;

-- governi e ministeri; gli incarichi di governo sono righe di office con target = ministero o governo
CREATE TABLE IF NOT EXISTS government (
  uri text PRIMARY KEY,                             -- it:gov:202
  name text NOT NULL, start_date date, end_date date, legislature int,
  source text NOT NULL, source_uri text
);
CREATE TABLE IF NOT EXISTS ministry (
  uri text PRIMARY KEY,                             -- it:gov:202:og202_665
  government text NOT NULL REFERENCES government (uri) ON DELETE CASCADE,
  name text NOT NULL, portfolio boolean,
  source text NOT NULL, source_uri text
);

-- la stessa persona con id diversi nelle due fonti (senatori: id della Camera e id del Senato)
CREATE TABLE IF NOT EXISTS person_same_as (
  person text NOT NULL,                             -- it:person:camera:309100
  same_as text NOT NULL,                            -- it:person:senato:17542
  method text NOT NULL,                             -- come è stata trovata: nome e cognome, cognome unico …
  PRIMARY KEY (person, same_as)
);
CREATE INDEX IF NOT EXISTS person_same_as_b ON person_same_as (same_as);

-- com'era il giorno D: gruppo (o componente del Misto) di ogni persona
CREATE OR REPLACE FUNCTION group_at(p text, d date) RETURNS text LANGUAGE sql STABLE AS $$
  SELECT m.grp FROM membership m JOIN grp g ON g.uri = m.grp
  WHERE m.person = p AND m.start_date <= d AND (m.end_date IS NULL OR m.end_date >= d)
  ORDER BY (g.kind = 'misto_component') DESC LIMIT 1
$$;

ALTER TABLE agenda_item ADD COLUMN IF NOT EXISTS stage text;        -- fase dell'esame ed esito (Bollettino)
ALTER TABLE agenda_item ADD COLUMN IF NOT EXISTS text text;          -- testo dell'argomento (ordine del giorno)
ALTER TABLE agenda_item ADD COLUMN IF NOT EXISTS scheduled_time text;
ALTER TABLE agenda_item ADD COLUMN IF NOT EXISTS rapporteurs text;

-- dagli argomenti agli atti, nei formati delle varie fonti (vedi sotto)
CREATE OR REPLACE FUNCTION lega_argomenti(prefisso text, leg int) RETURNS void LANGUAGE sql AS $$
  UPDATE agenda_item_act x SET act = a.uri FROM act a
  WHERE x.act IS NULL AND x.item LIKE prefisso || '%' AND a.chamber = split_part(prefisso, ':', 2) AND a.legislature = leg AND (
        -- progetti di legge: «ac:3148» (ordine del giorno, Bollettino), «pdl:2822-B» (resoconto d'Aula)
        (x.act_ref ~ '^(ac|pdl):' AND a.kind = 'bill' AND a.number = regexp_replace(split_part(x.act_ref, ':', 2), '-[A-Z]+(-bis|-ter)?$', ''))
        -- sindacato ispettivo: «aic:5-04321» (Bollettino), «mozione:1-00599» (resoconto d'Aula)
     OR (x.act_ref ~ '^(aic|mozione|interpellanza|interrogazione|risoluzione):'
         AND a.uri = 'it:camera:' || leg || ':aic:' || split_part(x.act_ref, ':', 2))
        -- Senato: «ddl:1353-B» (resoconto AKN), il numero esatto o quello della prima lettura
     OR (x.act_ref ~ '^ddl:' AND a.kind = 'bill'
         AND a.number IN (split_part(x.act_ref, ':', 2), regexp_replace(split_part(x.act_ref, ':', 2), '-[A-Z]+(-bis|-ter)?$', ''))));
$$;

CREATE TABLE IF NOT EXISTS speech (
  uri text PRIMARY KEY,
  item text NOT NULL REFERENCES agenda_item (uri) ON DELETE CASCADE,
  ord int NOT NULL,
  person text REFERENCES person (uri),             -- BY
  speaker_label text,                              -- come lo scrive il resoconto (PRESIDENTE, RICCARDO RICCIARDI)
  as_group text,                                   -- gruppo dichiarato nel resoconto alla data
  as_office text,
  kind text,                                       -- speech | reply | personal_statement | vote_explanation … (dopo)
  anchor text,
  hash text NOT NULL,
  text text NOT NULL,                              -- testo canonico: solo parlato
  markup text                                      -- XML originale dell'intervento
);
CREATE INDEX IF NOT EXISTS speech_person ON speech (person);
CREATE INDEX IF NOT EXISTS speech_fts ON speech USING gin (to_tsvector('italian', text));

CREATE TABLE IF NOT EXISTS segment (
  uri text PRIMARY KEY,
  speech text NOT NULL REFERENCES speech (uri) ON DELETE CASCADE,
  ord int NOT NULL,
  start_char int NOT NULL, end_char int NOT NULL,
  kind text NOT NULL,
  hash text NOT NULL
);

CREATE TABLE IF NOT EXISTS reaction (
  uri text PRIMARY KEY,
  speech text NOT NULL REFERENCES speech (uri) ON DELETE CASCADE,
  kind text NOT NULL,                              -- applause | protests | comments | interruption | procedure …
  offset_char int NOT NULL,
  raw text NOT NULL,
  from_raw text,                                   -- chi reagisce, come lo scrive il resoconto
  from_group text                                  -- uri del gruppo, quando risolto
);
CREATE INDEX IF NOT EXISTS reaction_kind ON reaction (kind);
-- chi reagisce, una riga per gruppo o persona: «Applausi dei deputati dei gruppi PD-IDP e AVS» ne ha due. kind e raw
-- vengono dal resoconto, grp e person li riempie lega_reazioni alla data della seduta. from_group in reaction resta
-- per le reazioni di un gruppo solo
CREATE TABLE IF NOT EXISTS reaction_from (
  reaction text NOT NULL REFERENCES reaction (uri) ON DELETE CASCADE,
  ord int NOT NULL,                                -- posizione della parte in chi reagisce
  kind text NOT NULL,                              -- group | person | office | chair
  raw text NOT NULL,                               -- come lo scrive il resoconto
  grp text,                                        -- gruppo o componente del Misto, quel giorno
  person text                                      -- chi reagisce, quando il resoconto nomina una persona
);
CREATE INDEX IF NOT EXISTS reaction_from_reaction ON reaction_from (reaction);
CREATE INDEX IF NOT EXISTS reaction_from_grp ON reaction_from (grp);

-- nomi dei gruppi confrontabili: minuscole, trattini senza spazi («Lega - Salvini Premier» = «Lega-Salvini Premier»)
CREATE OR REPLACE FUNCTION nome_gruppo(t text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT ' ' || btrim(regexp_replace(regexp_replace(lower(replace(t, '’', '''')), '\s*[-–—]\s*', '-', 'g'), '\s+', ' ', 'g')) || ' '
$$;

-- chi reagisce, alla data della seduta. Gruppi: i nomi (nome, sigla, alias, «Misto-» + nome per le componenti) dei
-- gruppi in carica quel giorno che compaiono nel testo, così un elenco «X, Y e Z» dà tre gruppi; un nome dentro uno più
-- lungo non conta («Misto» in «Misto-+Europa») e la componente prende il posto del Misto. Persone: cognome, o nome e
-- cognome, fra chi aveva il mandato in quel ramo (per le cariche di governo, chi aveva un incarico); con più candidati
-- vale chi parla nella seduta, e se il dubbio resta la riga resta senza persona. Tocca solo le righe non ancora legate:
-- dopo un'anagrafica nuova si rilancia su tutto (lega_reazioni('it:')).
CREATE OR REPLACE FUNCTION lega_reazioni(prefisso text) RETURNS void LANGUAGE sql AS $$
  WITH parti AS (
    SELECT f.reaction, f.ord, f.raw, nome_gruppo(f.raw) AS n, st.chamber, st.date
    FROM reaction_from f JOIN reaction r ON r.uri = f.reaction JOIN speech s ON s.uri = r.speech
    JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
    WHERE f.reaction LIKE prefisso || '%' AND f.kind = 'group' AND f.grp IS NULL),
  nomi AS (
    SELECT g.uri, g.chamber, g.part_of, g.start_date, g.end_date, btrim(nome_gruppo(x)) AS n
    FROM grp g, unnest(CASE WHEN g.kind = 'misto_component' THEN ARRAY['Misto-' || g.name, g.short_name] ELSE ARRAY[g.name, g.short_name] END
                       || coalesce(g.aliases, '{}')) x
    WHERE x IS NOT NULL AND length(x) >= 2),
  trovati AS (
    SELECT p.reaction, p.ord, p.raw, m.uri, m.part_of, strpos(p.n, m.n) AS a, length(m.n) AS l
    FROM parti p JOIN nomi m ON m.chamber = p.chamber AND (m.start_date IS NULL OR m.start_date <= p.date)
     AND (m.end_date IS NULL OR m.end_date >= p.date) AND strpos(p.n, m.n) > 0
    WHERE substr(p.n, strpos(p.n, m.n) - 1, 1) !~ '[[:alnum:]+]' AND substr(p.n, strpos(p.n, m.n) + length(m.n), 1) !~ '[[:alnum:]]'),
  tenuti AS (
    SELECT DISTINCT t.reaction, t.ord, t.raw, t.uri FROM trovati t
    WHERE NOT EXISTS (SELECT 1 FROM trovati u WHERE u.reaction = t.reaction AND u.ord = t.ord AND u.l > t.l AND u.a <= t.a AND u.a + u.l >= t.a + t.l)
      AND NOT EXISTS (SELECT 1 FROM trovati u WHERE u.reaction = t.reaction AND u.ord = t.ord AND u.part_of = t.uri)),
  via AS (
    DELETE FROM reaction_from f USING (SELECT DISTINCT reaction, ord FROM tenuti) x
    WHERE f.reaction = x.reaction AND f.ord = x.ord AND f.kind = 'group' AND f.grp IS NULL)
  INSERT INTO reaction_from (reaction, ord, kind, raw, grp) SELECT reaction, ord, 'group', raw, uri FROM tenuti;

  WITH parti AS (
    SELECT f.reaction, f.ord, f.kind, st.uri AS seduta, st.chamber, st.date,
           lower(CASE WHEN f.kind = 'office' THEN substring(f.raw from '([[:upper:]][[:alpha:]''’]+)$') ELSE f.raw END) AS chi
    FROM reaction_from f JOIN reaction r ON r.uri = f.reaction JOIN speech s ON s.uri = r.speech
    JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting
    WHERE f.reaction LIKE prefisso || '%' AND f.kind IN ('person', 'office') AND f.person IS NULL),
  cand AS (
    SELECT DISTINCT p.reaction, p.ord, pe.uri, p.seduta, p.date
    FROM parti p JOIN person pe ON lower(pe.family_name) = p.chi OR lower(pe.given_name || ' ' || pe.family_name) = p.chi
    WHERE EXISTS (SELECT 1 FROM mandate m WHERE m.person = pe.uri AND m.chamber = p.chamber AND m.start_date <= p.date
                  AND (m.end_date IS NULL OR m.end_date >= p.date))
       OR (p.kind = 'office' AND EXISTS (SELECT 1 FROM office o WHERE o.person = pe.uri AND o.start_date <= p.date
                                         AND (o.end_date IS NULL OR o.end_date >= p.date)))),
  scelti AS (
    SELECT c.reaction, c.ord, min(c.date) AS date,
           CASE WHEN count(*) = 1 THEN min(c.uri)
                WHEN count(*) FILTER (WHERE x.parla) = 1 THEN min(c.uri) FILTER (WHERE x.parla) END AS uri
    FROM cand c CROSS JOIN LATERAL (SELECT EXISTS (SELECT 1 FROM speech s JOIN agenda_item i ON i.uri = s.item
                                                   WHERE i.sitting = c.seduta AND s.person = c.uri) AS parla) x
    GROUP BY 1, 2)
  UPDATE reaction_from f SET person = s.uri, grp = group_at(s.uri, s.date) FROM scelti s
  WHERE f.reaction = s.reaction AND f.ord = s.ord AND f.kind IN ('person', 'office') AND f.person IS NULL AND s.uri IS NOT NULL;

  UPDATE reaction r SET from_group = x.g
  FROM (SELECT reaction, min(grp) AS g FROM reaction_from WHERE reaction LIKE prefisso || '%' AND grp IS NOT NULL
        GROUP BY 1 HAVING count(DISTINCT grp) = 1) x
  WHERE r.uri = x.reaction AND r.from_group IS DISTINCT FROM x.g;
$$;

-- chi o che cosa si cita in un intervento e non è in person: auditi, persone, aziende, enti, luoghi (dalla NER, dopo).
-- person resta l'anagrafica ufficiale (Camera, Senato, Governo)
CREATE TABLE IF NOT EXISTS entity (
  uri text PRIMARY KEY,                            -- it:entity:… oppure wikidata:Q…
  kind text NOT NULL,                              -- person | organization | place
  name text NOT NULL,
  wikidata text,
  source text
);
CREATE TABLE IF NOT EXISTS speech_mention (        -- MENTIONS: una riga per persona o entità citata
  speech text NOT NULL REFERENCES speech (uri) ON DELETE CASCADE,
  ord int NOT NULL,
  person text REFERENCES person (uri),
  entity text REFERENCES entity (uri),
  surface text,                                    -- come lo scrive il testo
  start_char int, end_char int,                    -- quando la fonte o la NER danno la posizione
  method text NOT NULL,                            -- fonte (link del resoconto) | ner
  PRIMARY KEY (speech, ord),
  CHECK ((person IS NULL) <> (entity IS NULL))
);
CREATE INDEX IF NOT EXISTS speech_mention_person ON speech_mention (person);
CREATE INDEX IF NOT EXISTS speech_mention_entity ON speech_mention (entity);

-- progetti di legge (Act) con iter, testi, firmatari, assegnazioni, relatori, abbinamenti e trasmissioni
CREATE TABLE IF NOT EXISTS act (
  uri text PRIMARY KEY,
  chamber text NOT NULL, legislature int NOT NULL,
  number text NOT NULL,
  kind text NOT NULL, kind_raw text, constitutional boolean,
  initiative text,                                  -- Parlamentare | Governo | Regioni | CNEL | Popolare | Mista …
  title text, date date, description text,
  law_number text, law_date date,                   -- la legge che ne è nata, se c'è
  status text, status_date date,                    -- ultimo passo dell'iter
  card_url text, text_urls text[],
  source text NOT NULL, source_uri text
);
CREATE INDEX IF NOT EXISTS act_fts ON act USING gin (to_tsvector('italian', coalesce(title, '')));
-- atti di sindacato ispettivo e di indirizzo (interrogazioni, mozioni, risoluzioni, ordini del giorno): testo e stato
ALTER TABLE act ADD COLUMN IF NOT EXISTS text text;
ALTER TABLE act ADD COLUMN IF NOT EXISTS closed_date date;
ALTER TABLE act ADD COLUMN IF NOT EXISTS concluded boolean;
ALTER TABLE act ADD COLUMN IF NOT EXISTS source_key text;   -- il file della fonte da cui viene (per sostituirlo intero)
CREATE INDEX IF NOT EXISTS act_kind ON act (chamber, legislature, kind);
CREATE INDEX IF NOT EXISTS act_text_fts ON act USING gin (to_tsvector('italian', coalesce(text, '')));
CREATE TABLE IF NOT EXISTS act_addressee (          -- ADDRESSED_TO: il ministero a cui l'atto è rivolto
  act text NOT NULL REFERENCES act (uri) ON DELETE CASCADE,
  ministry text NOT NULL,
  PRIMARY KEY (act, ministry)
);
CREATE TABLE IF NOT EXISTS act_subject (            -- SUBJECT: temi EuroVoc
  act text NOT NULL REFERENCES act (uri) ON DELETE CASCADE,
  concept text NOT NULL,
  PRIMARY KEY (act, concept)
);

CREATE TABLE IF NOT EXISTS act_step (               -- HAS_STEP
  uri text PRIMARY KEY,
  act text NOT NULL REFERENCES act (uri) ON DELETE CASCADE,
  ord int NOT NULL, title text, date date
);
CREATE TABLE IF NOT EXISTS act_version (            -- HAS_VERSION
  uri text PRIMARY KEY,
  act text NOT NULL REFERENCES act (uri) ON DELETE CASCADE,
  title text, date date, url text
);
CREATE TABLE IF NOT EXISTS act_sponsor (            -- SPONSORS
  act text NOT NULL REFERENCES act (uri) ON DELETE CASCADE,
  person text NOT NULL REFERENCES person (uri),
  first boolean NOT NULL,
  PRIMARY KEY (act, person)
);
ALTER TABLE act_sponsor ADD COLUMN IF NOT EXISTS as_office text;  -- per i membri del governo: Ministro della Difesa …
CREATE INDEX IF NOT EXISTS act_sponsor_person ON act_sponsor (person);
CREATE TABLE IF NOT EXISTS act_assignment (         -- ASSIGNED
  act text NOT NULL REFERENCES act (uri) ON DELETE CASCADE,
  body text NOT NULL, seat text, date date, title text
);
CREATE TABLE IF NOT EXISTS act_rapporteur (         -- RAPPORTEUR: la fonte dà solo il nome; la persona si trova al caricamento
  act text NOT NULL REFERENCES act (uri) ON DELETE CASCADE,
  name_raw text NOT NULL, role text, raw text,
  person text REFERENCES person (uri)
);
CREATE TABLE IF NOT EXISTS act_joint (              -- JOINED: abbinato all'atto portante
  act text NOT NULL REFERENCES act (uri) ON DELETE CASCADE,
  main_act text NOT NULL, text_type text,
  PRIMARY KEY (act, main_act)
);
CREATE TABLE IF NOT EXISTS act_transmission (       -- TRANSMITTED: passaggi all'altra Camera
  act text NOT NULL REFERENCES act (uri) ON DELETE CASCADE,
  other_ref text, date date, title text, provenance text
);

-- documenti: per ora gli allegati del Bollettino (proposte di parere, emendamenti, risoluzioni)
CREATE TABLE IF NOT EXISTS document (
  uri text PRIMARY KEY,
  kind text NOT NULL,                               -- annex | memorandum | dossier | judgment …
  date date, body_code text, body text,
  title text, anchor text, acts text[],
  hash text NOT NULL, text text,
  source text NOT NULL, source_key text,
  loaded_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE document ADD COLUMN IF NOT EXISTS url text;
ALTER TABLE document ADD COLUMN IF NOT EXISTS format text;
ALTER TABLE document ADD COLUMN IF NOT EXISTS author_raw text;          -- chi l'ha mandato, come lo scrive la Camera («UIL FP»)
ALTER TABLE document ADD COLUMN IF NOT EXISTS hearing text;             -- l'audizione o l'esame per cui è stato depositato
ALTER TABLE document ADD COLUMN IF NOT EXISTS sitting_date date;
ALTER TABLE document ADD COLUMN IF NOT EXISTS third_party boolean;
ALTER TABLE document ADD COLUMN IF NOT EXISTS code text;                -- codice del documento (dossier: AC0550, AS0473b …)      -- scritto di terzi: nel sito solo estratti con link
CREATE INDEX IF NOT EXISTS document_fts ON document USING gin (to_tsvector('italian', coalesce(text, '')));

-- da nome a organo: confronto senza accenti, apostrofi, maiuscole e spazi
CREATE OR REPLACE FUNCTION norm_nome(t text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT regexp_replace(lower(translate(coalesce(t, ''), 'àèéìòùÀÈÉÌÒÙ', 'aeeiouAEEIOU')), '[^a-z]', '', 'g')
$$;

-- video della WebTV: un Video per seduta e i tratti degli interventi (HAS_VIDEO) con secondi di inizio e fine
CREATE TABLE IF NOT EXISTS video (
  uri text PRIMARY KEY,
  event_id int NOT NULL, sitting text, kind text, title text, url text NOT NULL,
  start_ts timestamp, end_ts timestamp,
  source text NOT NULL, source_key text
);
CREATE INDEX IF NOT EXISTS video_sitting ON video (sitting);
CREATE TABLE IF NOT EXISTS video_segment (
  video text NOT NULL REFERENCES video (uri) ON DELETE CASCADE,
  ord int NOT NULL,
  speech text,                                      -- uri dell'intervento del resoconto (si lega quando il resoconto c'è)
  anchor text, label text,
  start_s int, end_s int, clock timestamp,
  PRIMARY KEY (video, ord)
);
CREATE INDEX IF NOT EXISTS video_segment_speech ON video_segment (speech);

-- emendamenti (Amendment) e firmatari (SIGNS): una riga per proposta in ogni sede (commissione, Aula)
CREATE TABLE IF NOT EXISTS amendment (
  uri text PRIMARY KEY,                             -- it:camera:19:ac:3131:eme:com746:1.1
  act text NOT NULL,                                -- il progetto di legge
  number text NOT NULL, kind text, action text, article text,
  venue text,                                       -- referente | assembly | …
  committee text, sitting_number int, sitting_date date,
  group_title text, status text, outcome text,      -- esito: inammissibile, approvato, respinto, ritirato …
  decree text, identical text[],
  hash text NOT NULL, text text,
  source_key text NOT NULL
);
CREATE INDEX IF NOT EXISTS amendment_act ON amendment (act);
ALTER TABLE amendment ADD COLUMN IF NOT EXISTS presented date;      -- data di presentazione (Senato)
CREATE TABLE IF NOT EXISTS amendment_signer (
  amendment text NOT NULL REFERENCES amendment (uri) ON DELETE CASCADE,
  ord int NOT NULL,
  person text,                                      -- deputato; vuoto per governo e relatori senza id
  first boolean, family_raw text, given_raw text, kind_raw text,
  PRIMARY KEY (amendment, ord)
);
CREATE INDEX IF NOT EXISTS amendment_signer_person ON amendment_signer (person);

-- testi dei progetti di legge, per versione (il codice dello stampato: leg.19.pdl.camera.3148.19PDL0218420).
-- Tabelle a parte e non colonne di act_version: gli atti si ricaricano interi quando cambia l'iter, i testi no.
CREATE TABLE IF NOT EXISTS act_text (
  code text PRIMARY KEY,
  hash text NOT NULL, text text NOT NULL,
  source_key text NOT NULL
);
CREATE INDEX IF NOT EXISTS act_text_fts ON act_text USING gin (to_tsvector('italian', text));
ALTER TABLE act_text ADD COLUMN IF NOT EXISTS act text;            -- Senato: l'atto della versione (la Camera la lega con act_version)
ALTER TABLE act_text ADD COLUMN IF NOT EXISTS kind text;           -- Senato: presented | committee | message
CREATE TABLE IF NOT EXISTS act_article (
  code text NOT NULL REFERENCES act_text (code) ON DELETE CASCADE,
  ord int NOT NULL, number text, anchor text, text text,
  PRIMARY KEY (code, ord)
);
CREATE TABLE IF NOT EXISTS act_citation (           -- CITES: le norme citate, con l'URN di Normattiva
  code text NOT NULL REFERENCES act_text (code) ON DELETE CASCADE,
  urn text NOT NULL, label text,
  PRIMARY KEY (code, urn)
);
-- versione -> codice dello stampato (la versione ha uri «…:vta19_<codice>»)
CREATE OR REPLACE VIEW act_version_text AS
SELECT v.uri AS version, v.act, v.title, v.date, t.code, t.text
FROM act_version v JOIN act_text t ON v.uri LIKE '%:vta%\_' || t.code;

-- votazioni elettroniche (Vote) e voto di ogni parlamentare (VOTED). La seduta è un riferimento, non una chiave esterna:
-- i voti possono arrivare prima del resoconto.
CREATE TABLE IF NOT EXISTS vote (
  uri text PRIMARY KEY,
  sitting text NOT NULL,
  chamber text NOT NULL, legislature int NOT NULL,
  number int NOT NULL, date date NOT NULL,
  title text, description text,
  kind text NOT NULL, kind_raw text,            -- final | article | amendment | agenda_order | motion | resolution …
  favor int, against int, abstain int, present int, voting int, majority int,
  approved boolean, secret boolean, final boolean, confidence boolean,
  presided_by text,
  source text NOT NULL, source_uri text, source_url text, source_key text, source_hash text,
  loaded_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE vote ADD COLUMN IF NOT EXISTS ballots_match boolean;  -- i voti dei singoli tornano con i totali pubblicati? (null se segreta)
CREATE INDEX IF NOT EXISTS vote_sitting ON vote (sitting);
CREATE INDEX IF NOT EXISTS vote_date ON vote (chamber, date);

CREATE TABLE IF NOT EXISTS vote_act (              -- ON: l'atto votato, per ora come riferimento della fonte (ac19_80, aic9_00080_004_19)
  vote text NOT NULL REFERENCES vote (uri) ON DELETE CASCADE,
  act_ref text NOT NULL,
  act text,                                         -- uri dell'atto, quando il connettore degli atti lo risolve
  PRIMARY KEY (vote, act_ref)
);

CREATE TABLE IF NOT EXISTS ballot (
  vote text NOT NULL REFERENCES vote (uri) ON DELETE CASCADE,
  person text NOT NULL REFERENCES person (uri),
  result text NOT NULL,                             -- favor | against | abstain | absent | mission | chair | voted (segreto)
  result_raw text, note text,
  grp text,                                         -- gruppo o componente del Misto attribuiti dalla Camera in quel voto
  PRIMARY KEY (vote, person)
);
CREATE INDEX IF NOT EXISTS ballot_person ON ballot (person);

-- vista comoda per i conti sugli scontri: chi reagisce, a chi, in quale seduta
CREATE OR REPLACE VIEW reaction_flow AS
SELECT r.kind, r.from_raw AS da, s.as_group AS verso, st.date, st.chamber, r.speech
FROM reaction r JOIN speech s ON s.uri = r.speech JOIN agenda_item i ON i.uri = s.item JOIN sitting st ON st.uri = i.sitting;

-- membri del governo che parlano al Senato senza esserne membri: senato.it dà loro un id proprio, senza anagrafica.
-- Si legano alla scheda del governo (dalla Camera): per ogni intervento, i membri del governo in carica alla data con
-- il cognome scritto prima della virgola («PIANTEDOSI, ministro dell'interno»); l'id si lega a chi copre almeno il 90%
-- dei suoi interventi (la fonte a volte sbaglia il nome: Savino scritta «ALBANO» in 2 interventi su 79).
CREATE OR REPLACE FUNCTION lega_governo(prefisso text) RETURNS void LANGUAGE sql AS $$
  WITH interventi AS (
    SELECT s.uri, s.person AS senato, s.speaker_label, t.date
    FROM speech s JOIN person p0 ON p0.uri = s.person AND p0.family_name IS NULL
    JOIN agenda_item i ON i.uri = s.item JOIN sitting t ON t.uri = i.sitting
    WHERE s.uri LIKE prefisso || '%' AND s.person LIKE 'it:person:senato:%' AND s.as_office IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM person_same_as x WHERE x.same_as = s.person)),
  candidati AS (
    SELECT DISTINCT n.uri, n.senato, o.person AS persona
    FROM interventi n JOIN office o ON o.target LIKE 'it:gov:%' AND o.start_date <= n.date AND (o.end_date IS NULL OR o.end_date >= n.date)
    JOIN person p ON p.uri = o.person AND norm_nome(p.family_name) = norm_nome(split_part(n.speaker_label, ',', 1))),
  quote AS (
    SELECT c.senato, c.persona, count(*) AS k, (SELECT count(*) FROM interventi n WHERE n.senato = c.senato) AS tot
    FROM candidati c GROUP BY 1, 2)
  INSERT INTO person_same_as (person, same_as, method)
  SELECT persona, senato, 'governo: carica alla data e cognome' FROM quote WHERE k >= 0.9 * tot
  ON CONFLICT DO NOTHING;
$$;

-- gruppi nei voti della Camera: il voto porta a volte l'id di una versione del gruppo dopo un cambio di nome (gr4212
-- per Azione, gr4291 per Italia Viva…) o del Misto senza componente (cgm4111), che dati.camera.it non descrive.
-- L'id si lega al gruppo che i votanti hanno alla data in almeno il 95% dei voti; gli altri (gr9999, segnaposto dei
-- deputati appena proclamati) restano e si legge il gruppo alla data.
CREATE TABLE IF NOT EXISTS grp_alias (
  alias text PRIMARY KEY,
  grp text NOT NULL REFERENCES grp (uri) ON DELETE CASCADE,
  share real NOT NULL,
  method text NOT NULL
);
CREATE OR REPLACE FUNCTION lega_gruppi_voti() RETURNS void LANGUAGE sql AS $$
  WITH x AS (SELECT b.grp AS alias, group_at(b.person, v.date) AS g FROM ballot b JOIN vote v ON v.uri = b.vote
             WHERE NOT EXISTS (SELECT 1 FROM grp WHERE uri = b.grp)),
  conti AS (SELECT alias, g, count(*) AS n, sum(count(*)) OVER (PARTITION BY alias) AS tot FROM x WHERE g IS NOT NULL GROUP BY 1, 2)
  INSERT INTO grp_alias (alias, grp, share, method)
  SELECT alias, g, n::real / tot, 'gruppo dei votanti alla data' FROM conti WHERE n >= 0.95 * tot
  ON CONFLICT (alias) DO UPDATE SET grp = excluded.grp, share = excluded.share;
$$;

-- ordini del giorno votati alla Camera: il voto scrive «aic9_00643_BIS_193_19», l'atto «9/00643-bis-AR/193» (la
-- lettera del testo esaminato manca o è diversa). Si confrontano il numero (con bis/ter) e l'ordine, e si prende
-- l'ordine del giorno presentato più di recente prima del voto, solo se è uno.
CREATE OR REPLACE FUNCTION base_odg(g text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN lower(g) ~ '^doc' THEN regexp_replace(lower(g), '[^a-z0-9]', '', 'g')
              ELSE regexp_replace(g, '\D', '', 'g') || coalesce(substring(lower(g) from '(bis|ter|quater)'), '') END
$$;
CREATE OR REPLACE FUNCTION lega_odg_voti(leg int) RETURNS void LANGUAGE sql AS $$
  WITH rif AS (
    SELECT x.vote, x.act_ref, vo.date AS vdate, split_part(substr(x.act_ref, 4), '_', 1) AS tipo,
           base_odg(regexp_replace(substr(x.act_ref, 4), '^\d_(.*)_\d+_' || leg || '$', '\1')) AS base,
           regexp_replace(x.act_ref, '^.*_(\d+)_' || leg || '$', '\1') AS ord
    FROM vote_act x JOIN vote vo ON vo.uri = x.vote
    WHERE x.act IS NULL AND x.act_ref LIKE 'aic%' AND vo.chamber = 'camera' AND vo.legislature = leg),
  cand AS (
    SELECT r.vote, r.act_ref, a.uri, a.date, max(a.date) OVER (PARTITION BY r.vote, r.act_ref) AS ultima
    FROM rif r JOIN act a ON a.chamber = 'camera' AND a.legislature = leg AND a.number ~ '^\d/.+/\d+$'
     AND split_part(a.number, '/', 1) = r.tipo AND regexp_replace(a.number, '^.*/(\d+)$', '\1') = r.ord
     AND base_odg(regexp_replace(a.number, '^\d/(.*)/\d+$', '\1')) = r.base AND a.date <= r.vdate),
  unici AS (SELECT vote, act_ref, min(uri) AS uri FROM cand WHERE date = ultima GROUP BY 1, 2 HAVING count(*) = 1)
  UPDATE vote_act v SET act = u.uri FROM unici u WHERE v.vote = u.vote AND v.act_ref = u.act_ref;
$$;

-- concetti dei thesauri: EuroVoc (temi di interrogazioni e mozioni, da dati.camera.it) e, in seguito, TESEO (Senato).
-- act_subject.concept è l'indirizzo del concetto: il nome si legge da qui
CREATE TABLE IF NOT EXISTS concept (
  uri text PRIMARY KEY,                            -- http://eurovoc.europa.eu/659
  scheme text NOT NULL,                            -- eurovoc | teseo
  label_it text NOT NULL, label_en text,
  broader text[],                                  -- concetti più generali dello stesso thesaurus
  source text NOT NULL
);
CREATE INDEX IF NOT EXISTS concept_label ON concept (scheme, lower(label_it));

-- indici sulle chiavi esterne: senza, cancellare una seduta per ricaricarla scorre per intero speech e segment a ogni
-- intervento (ON DELETE CASCADE), e il caricamento di 1.085 sedute d'Aula supera le due ore (2/11/2026)
CREATE INDEX IF NOT EXISTS agenda_item_sitting ON agenda_item (sitting);
CREATE INDEX IF NOT EXISTS speech_item ON speech (item);
CREATE INDEX IF NOT EXISTS segment_speech ON segment (speech);
CREATE INDEX IF NOT EXISTS reaction_speech ON reaction (speech);
CREATE INDEX IF NOT EXISTS act_step_act ON act_step (act);
CREATE INDEX IF NOT EXISTS act_version_act ON act_version (act);
CREATE INDEX IF NOT EXISTS act_assignment_act ON act_assignment (act);
CREATE INDEX IF NOT EXISTS act_rapporteur_act ON act_rapporteur (act);
CREATE INDEX IF NOT EXISTS act_transmission_act ON act_transmission (act);
CREATE INDEX IF NOT EXISTS membership_grp ON membership (grp);
CREATE INDEX IF NOT EXISTS seat_body ON seat (body);

-- collegamenti fra concetti di thesauri diversi (oggi TESEO -> EuroVoc). I concetti restano distinti: la relazione dice
-- il tipo di legame (SKOS, visto dal concetto di partenza), con quale metodo è nata, quanto è sicura e se una persona
-- l'ha verificata. Fra la stessa coppia possono esserci più righe, una per metodo. Dati in dati/allineamenti/
CREATE TABLE IF NOT EXISTS concept_match (
  from_concept text NOT NULL,                      -- http://dati.senato.it/teseo/00002560
  to_concept text NOT NULL,                        -- http://eurovoc.europa.eu/2825
  relation text NOT NULL,                          -- exactMatch | closeMatch | broadMatch | narrowMatch | relatedMatch
  confidence text,                                 -- alta | media | bassa
  score real,                                      -- per i metodi che danno un punteggio
  method text NOT NULL,                            -- «proposto da Claude (claude-opus-5-5), 2/11/2026», «stesso nome» …
  verified boolean, verified_by text, verified_at date,
  PRIMARY KEY (from_concept, to_concept, relation, method)
);
CREATE INDEX IF NOT EXISTS concept_match_to ON concept_match (to_concept);

-- ricerca per significato (10-decisioni/2026-11-03-modello-ricerca-significato): brani di circa 1.500 caratteri
-- tagliati a fine frase, vettori text-embedding-3-large a 1.024 dimensioni. pipeline/vettori.py li riempie.
-- passage senza REFERENCES speech: il caricamento cancella e ricarica le sedute cambiate, e «taglia» rifà solo
-- i brani degli interventi il cui hash non torna più. I vettori stanno a parte, per impronta del testo del brano:
-- sopravvivono ai ricaricamenti e un brano uguale non si paga due volte.
CREATE TABLE IF NOT EXISTS passage (
  speech text NOT NULL,
  speech_hash text NOT NULL,                       -- hash dell'intervento quando è stato tagliato
  ord int NOT NULL,
  start_char int NOT NULL, end_char int NOT NULL,  -- posizioni in speech.text, da 0, fine esclusa
  hash text NOT NULL,                              -- sha256 del testo del brano
  PRIMARY KEY (speech, ord)
);
CREATE INDEX IF NOT EXISTS passage_hash ON passage (hash);

CREATE TABLE IF NOT EXISTS passage_vector (
  hash text NOT NULL,
  model text NOT NULL,                             -- text-embedding-3-large
  embedding vector(1024) NOT NULL,
  PRIMARY KEY (hash, model)
);

CREATE TABLE IF NOT EXISTS vector_batch (           -- i lavori della Batch API di OpenAI
  id text PRIMARY KEY,                             -- batch_…
  model text NOT NULL,
  status text NOT NULL,                            -- inviato | completed | failed | expired | cancelled
  hashes text[] NOT NULL,                          -- in ordine: la richiesta k porta i brani da k*100
  sent_at timestamptz NOT NULL DEFAULT now(),
  collected_at timestamptz,
  tokens bigint,
  error text
);
