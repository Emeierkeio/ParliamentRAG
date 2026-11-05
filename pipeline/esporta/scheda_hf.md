---
license: cc-by-sa-4.0
language:
  - it
pretty_name: "ParliamentRAG — Italian Parliament, 19th legislature"
size_categories:
  - 1M<n<10M
task_categories:
  - text-retrieval
  - question-answering
tags:
  - parliament
  - politics
  - italy
  - legal
  - knowledge-graph
  - rag
configs:
  - config_name: speeches
    data_files: speeches.parquet
    default: true
  - config_name: sessions
    data_files: sessions.parquet
  - config_name: debates
    data_files: debates.parquet
  - config_name: votes
    data_files: votes.parquet
  - config_name: individual_votes
    data_files: individual_votes.parquet
  - config_name: persons
    data_files: persons.parquet
  - config_name: mandates
    data_files: mandates.parquet
  - config_name: organizations
    data_files: organizations.parquet
  - config_name: memberships
    data_files: memberships.parquet
  - config_name: acts
    data_files: acts.parquet
  - config_name: act_sponsors
    data_files: act_sponsors.parquet
  - config_name: act_joints
    data_files: act_joints.parquet
  - config_name: act_subjects
    data_files: act_subjects.parquet
  - config_name: amendments
    data_files: amendments.parquet
---

# ParliamentRAG — Italian Parliament, 19th legislature

The work of both houses of the Italian Parliament, the Chamber of Deputies (Camera dei deputati) and the Senate (Senato della Repubblica), in the 19th legislature: sittings of the floor and of the committees, full speech transcripts, roll-call votes with every individual ballot, acts with their signatories and EuroVoc subjects, amendments, and the members with their mandates, groups and committees.

Data as of: Chamber {{DATI_CAMERA}}, Senate {{DATI_SENATO}} (last sitting held). Exported on {{GENERATED}}. The tables are refreshed every night from the same database that serves [www.parliamentrag.it](https://www.parliamentrag.it), which is loaded from the official open data of the two houses ([dati.camera.it](https://dati.camera.it), [dati.senato.it](https://dati.senato.it)) and from their records. The export code is public: [pipeline/esporta](https://github.com/Emeierkeio/ParliamentRAG/tree/main/pipeline/esporta). A monthly RDF version is archived on Zenodo: [10.5281/zenodo.21560331](https://doi.org/10.5281/zenodo.21560331).

All content is in Italian.

## Tables

| Table | Rows | Contents |
| --- | ---: | --- |
| `speeches` | {{N_SPEECHES}} | Full text of every speech on the floor and in committee, with date, sitting, agenda item, speaker and the group the record gives |
| `sessions` | {{N_SESSIONS}} | Sittings of the floor and of the committees, with the link to the official record |
| `debates` | {{N_DEBATES}} | Agenda items of each sitting |
| `votes` | {{N_VOTES}} | Roll-call votes: subject, kind, outcome, totals, acts voted on |
| `individual_votes` | {{N_INDIVIDUAL_VOTES}} | One row per (member, vote) with the individual ballot and the group |
| `persons` | {{N_PERSONS}} | Deputies, senators and government members: birth, education, profession, official and Wikidata identifiers |
| `mandates` | {{N_MANDATES}} | Terms of office in each house, with constituency |
| `organizations` | {{N_ORGANIZATIONS}} | Parliamentary groups, Mixed Group components, the floor and the committees |
| `memberships` | {{N_MEMBERSHIPS}} | Person–organization spells with role and dates |
| `acts` | {{N_ACTS}} | Bills, motions, resolutions, orders of the day, questions and other acts, with status and resulting law |
| `act_sponsors` | {{N_ACT_SPONSORS}} | Signatories of each act (`first` = first signatory) |
| `act_joints` | {{N_ACT_JOINTS}} | Acts examined jointly with a main act (abbinati) |
| `act_subjects` | {{N_ACT_SUBJECTS}} | Act → EuroVoc concept, with Italian and English labels |
| `amendments` | {{N_AMENDMENTS}} | Amendments in committee and on the floor: text, article, venue, outcome, signatories |

Identifiers are shared across tables: `id` of `sessions` is `session` elsewhere, `id` of `votes` is `vote`, persons are `person` (e.g. `it:person:camera:302940`, `it:person:senato:32`; `source_uri` gives the official dati.camera.it or dati.senato.it URI, `same_as` the same person in the other house). The `chamber` column is `camera` or `senato`.

Ballot results in `individual_votes` are `favor`, `against`, `abstain`, `absent`, `mission`, `chair`, `present_not_voting` and, for secret ballots, `voted` (who voted for or against is not public).

Committee sittings often have no verbatim record: their speeches come from the official summary (`kind = summary`, from the Chamber's Bollettino or the Senate's summary record), not from a transcript.

Not included: embeddings, user conversations, AI-written summaries.

## Example

```python
from datasets import load_dataset

speeches = load_dataset("emeierkeio/parliamentrag-leg19", "speeches", split="train")
senate = speeches.filter(lambda row: row["chamber"] == "senato")
```

## License and citation

Chamber data are CC BY-SA 4.0, Senate data CC BY 3.0: the tables are released under CC BY-SA 4.0, as the ShareAlike clause requires. ParliamentRAG is an independent research project of the University of Milano-Bicocca (Mirko Tritella, Riccardo Pozzi, Matteo Palmonari). It is not an official service of the Italian Parliament.

> Tritella, Pozzi, Palmonari. *Who Speaks Matters: Authority-Aware Multi-View RAG over Italian Parliamentary Proceedings.* The Semantic Web – ISWC 2026. doi:[10.1007/978-3-032-42029-9_24](https://doi.org/10.1007/978-3-032-42029-9_24)
