"""Riparazione rename gruppo parlamentare (Italia Viva → Casa Riformista).

Il 2026 il gruppo "ITALIA VIVA-IL CENTRO-RENEW EUROPE" si è rinominato in
"ITALIA VIVA-CASA RIFORMISTA (IV-CR)". L'ingest fa MERGE dei gruppi per nome,
quindi la nuova denominazione ha creato un secondo nodo con l'intera storia
delle membership replicata; le membership del nodo vecchio sono rimaste
aperte. Risultato: ogni deputato IV aveva due membership aperte verso due
nodi diversi, e l'attribuzione partito dei chunk diventava arbitraria
(Faraone finiva nel Misto).

La cura: verificare che ogni membership del nodo vecchio abbia la gemella
(stesso deputato, stesse date) sul nodo nuovo, poi DETACH DELETE del nodo
vecchio. La fonte emette ormai solo la denominazione nuova, quindi il nodo
non si ricrea agli update successivi.

Uso:  backend/venv/bin/python build/repair_group_rename.py [--execute]
      (senza --execute fa solo le verifiche)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.services.neo4j_client import Neo4jClient  # noqa: E402

OLD_NAME = "ITALIA VIVA-IL CENTRO-RENEW EUROPE"
NEW_NAME = "ITALIA VIVA-CASA RIFORMISTA (IV-CR)"


def main() -> None:
    execute = "--execute" in sys.argv
    settings = get_settings()
    print(f"DB: {settings.neo4j_uri}")
    client = Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )

    # Guardia 0: entrambi i nodi esistono
    counts = {
        r["name"]: r["n"] for r in client.query(
            "MATCH (g:ParliamentaryGroup) WHERE g.name IN [$old, $new] "
            "OPTIONAL MATCH (g)<-[m:MEMBER_OF_GROUP]-() "
            "RETURN g.name AS name, count(m) AS n",
            {"old": OLD_NAME, "new": NEW_NAME})
    }
    print(f"Membership: vecchio={counts.get(OLD_NAME)}, nuovo={counts.get(NEW_NAME)}")
    if OLD_NAME not in counts:
        print("Nodo vecchio assente: niente da riparare.")
        return
    if NEW_NAME not in counts:
        sys.exit("ABORT: nodo nuovo assente, il rename non è ancora ingerito qui.")

    # Guardia 1: il vecchio nodo ha SOLO relazioni MEMBER_OF_GROUP
    other_rels = client.query(
        "MATCH (g:ParliamentaryGroup {name: $old})-[r]-() "
        "WHERE type(r) <> 'MEMBER_OF_GROUP' "
        "RETURN type(r) AS rel, count(*) AS n", {"old": OLD_NAME})
    if other_rels:
        sys.exit(f"ABORT: relazioni inattese sul nodo vecchio: {other_rels}")

    # Guardia 2: ogni membership del vecchio ha la gemella sul nuovo
    orphans = client.query("""
        MATCH (d)-[m1:MEMBER_OF_GROUP]->(:ParliamentaryGroup {name: $old})
        WHERE NOT EXISTS {
          MATCH (d)-[m2:MEMBER_OF_GROUP]->(:ParliamentaryGroup {name: $new})
          WHERE m2.start_date = m1.start_date
            AND coalesce(toString(m2.end_date),'') = coalesce(toString(m1.end_date),'')
        }
        RETURN d.last_name AS dep, toString(m1.start_date) AS start,
               toString(m1.end_date) AS end
        """, {"old": OLD_NAME, "new": NEW_NAME})
    if orphans:
        sys.exit(f"ABORT: membership del vecchio senza gemella sul nuovo: {orphans}")
    print("Verifiche OK: vecchio ⊆ nuovo, nessun'altra relazione.")

    if not execute:
        print("Dry-run: aggiungi --execute per cancellare il nodo vecchio.")
        return

    client.query(
        "MATCH (g:ParliamentaryGroup {name: $old}) DETACH DELETE g",
        {"old": OLD_NAME})
    left = client.query(
        "MATCH (g:ParliamentaryGroup {name: $old}) RETURN count(g) AS n",
        {"old": OLD_NAME})
    print(f"Nodo vecchio cancellato (residui: {left[0]['n']}).")

    # Post-check: nessun deputato con più di una membership aperta
    doubles = client.query("""
        MATCH (d:Deputy)-[m:MEMBER_OF_GROUP]->(:ParliamentaryGroup)
        WHERE m.end_date IS NULL
        WITH d, count(m) AS n WHERE n > 1
        RETURN d.last_name AS dep, n""")
    print(f"Deputati con doppia membership aperta dopo il repair: {doubles or 'nessuno'}")

    client.close()


if __name__ == "__main__":
    main()
