"""
Script per popolare i ruoli istituzionali dei deputati e membri del governo in Neo4j.

Funzionalità:
1. Aggiorna le proprietà 'ruoloIstituzionale', 'tipoRuolo' sui nodi Deputato e MembroGoverno.
2. Crea relazioni semantiche grafo per ruoli chiave:
   - (Soggetto)-[:È_PRESIDENTE]->(GruppoParlamentare)
   - (Soggetto)-[:È_PRESIDENTE|:È_VICEPRESIDENTE|:È_SEGRETARIO]->(Commissione)
   - (MembroGoverno)-[:RIFERIMENTO_GOVERNO]->(Commissione)

Configurazione ruoli da backend/app_config.py
"""

from neo4j import GraphDatabase
import sys
import os

# Configurazione Neo4j
NEO4J_URI = "bolt://localhost:7688"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "thesis2026"

# Aggiungi la cartella backend al path per importare app_config
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    from app_config import GOVERNMENT_ROLES, PARLIAMENT_ROLES, CAPIGRUPPO, COMMISSION_ROLES
except ImportError:
    print("Errore: Impossibile importare app_config. Assicurati che il file backend/app_config.py esista.")
    sys.exit(1)


class RuoliLoader:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def clear_ruoli(self):
        """Rimuove i ruoli esistenti e le relazioni create da questo script."""
        with self.driver.session() as session:
            # Rimuove proprietà da entrambi i tipi di nodi
            session.run("""
                MATCH (d)
                WHERE d:Deputato OR d:MembroGoverno
                REMOVE d.ruoloIstituzionale, d.tipoRuolo, d.commissioneRuolo
            """)
            
            # Rimuove relazioni specifiche di ruolo
            session.run("""
                MATCH (d)-[r:È_PRESIDENTE|È_VICEPRESIDENTE|È_SEGRETARIO|RIFERIMENTO_GOVERNO]->()
                WHERE d:Deputato OR d:MembroGoverno
                DELETE r
            """)
            print("Proprietà ruoli e relazioni gerarchiche rimosse.")

    def find_deputato(self, session, full_name: str):
        """
        Cerca un deputato o membro del governo per cognome e nome.
        Gestisce cognomi composti e nomi multipli.
        """
        parts = full_name.strip().upper().split()
        if len(parts) < 2:
            return None

        # Strategia 1: MATCH (d) WHERE (d:Deputato OR d:MembroGoverno) AND d.cognome + d.nome match totalità parts
        # Proviamo a dividere parts in due blocchi (i, N-i)
        for i in range(1, len(parts)):
            cognome_try = " ".join(parts[:i])
            nome_try = " ".join(parts[i:])
            
            query = """
            MATCH (d)
            WHERE (d:Deputato OR d:MembroGoverno)
              AND toUpper(d.cognome) = $cognome
              AND toUpper(d.nome) STARTS WITH $nome
            RETURN d.id as id LIMIT 1
            """
            result = session.run(query, cognome=cognome_try, nome=nome_try)
            if record := result.single():
                return record['id']

        # Strategia 2: Fallback incrociato con STARTS WITH
        # Gestisce casi come "BOSCHI MARIA ELENA" -> d.cognome="BOSCHI", d.nome="MARIA ELENA"
        query_fallback = """
        MATCH (d)
        WHERE (d:Deputato OR d:MembroGoverno)
          AND ( (toUpper(d.cognome) = $c1 AND toUpper(d.nome) STARTS WITH $n1) OR
                (toUpper(d.cognome) = $c2 AND toUpper(d.nome) STARTS WITH $n2) )
        RETURN d.id as id LIMIT 1
        """
        # Prova le due combinazioni base se ci sono almeno 2 parole
        c1, n1 = parts[0], " ".join(parts[1:])
        c2, n2 = " ".join(parts[:-1]), parts[-1]
        
        result = session.run(query_fallback, c1=c1, n1=n1, c2=c2, n2=n2)
        if record := result.single():
            return record['id']

        return None

    def update_proprietà_ruolo(self, session, deputato_id: str, ruolo_str: str, tipo_ruolo: str, commissione_str: str = None):
        """Imposta le proprietà stringa sul nodo (Deputato o MembroGoverno)."""
        params = {
            'id': deputato_id,
            'ruolo': ruolo_str,
            'tipo_ruolo': tipo_ruolo,
            'commissione': commissione_str 
        }
        
        session.run("""
            MATCH (d)
            WHERE (d:Deputato OR d:MembroGoverno) AND d.id = $id
            SET d.ruoloIstituzionale = $ruolo,
                d.tipoRuolo = $tipo_ruolo,
                d.commissioneRuolo = $commissione
        """, **params)

    def create_relazione_gerarchica(self, session, deputato_id: str, target_name: str, target_label: str, ruolo_type: str):
        """Crea una relazione grafo verso un'entità."""
        rel_type = None
        if "Presidente" in ruolo_type and "Vice" not in ruolo_type:
            rel_type = "È_PRESIDENTE"
        elif "Vicepresidente" in ruolo_type:
            rel_type = "È_VICEPRESIDENTE"
        elif "Segretario" in ruolo_type:
            rel_type = "È_SEGRETARIO"
        elif "Riferimento Governo" in ruolo_type:
            rel_type = "RIFERIMENTO_GOVERNO"
        
        if not rel_type:
            return False

        query = f"""
            MATCH (d)
            WHERE (d:Deputato OR d:MembroGoverno) AND d.id = $dep_id
            MATCH (target:{target_label})
            WHERE target.nome = $target_name
            MERGE (d)-[:{rel_type}]->(target)
            RETURN count(*) as c
        """
        result = session.run(query, dep_id=deputato_id, target_name=target_name)
        if result.single()['c'] > 0:
            return True

        if target_label == 'GruppoParlamentare':
             query_fuzzy = f"""
                MATCH (d)
                WHERE (d:Deputato OR d:MembroGoverno) AND d.id = $dep_id
                MATCH (target:{target_label})
                WHERE target.nome CONTAINS $target_name
                MERGE (d)-[:{rel_type}]->(target)
                RETURN count(*) as c
             """
             result = session.run(query_fuzzy, dep_id=deputato_id, target_name=target_name)
             return result.single()['c'] > 0
             
        return False

    def reconcile_orphan_interventions(self, session):
        """
        Collega gli interventi che non hanno un link PRONUNCIATO_DA 
        basandosi sulla corrispondenza del nome con i nodi Deputato/MembroGoverno.
        """
        print("\nRiconciliazione interventi orfani per nome...")
        query = """
        MATCH (i:Speech)
        WHERE NOT (i)-[:SPOKEN_BY]->()
        WITH i, toUpper(i.surname_name) as full_name
        MATCH (d)
        WHERE (d:Deputy OR d:GovernmentMember)
          AND (toUpper(d.last_name + ' ' + d.first_name) = full_name OR toUpper(d.first_name + ' ' + d.last_name) = full_name)
        MERGE (i)-[:SPOKEN_BY]->(d)
        RETURN count(DISTINCT i) as recovered
        """
        result = session.run(query)
        record = result.single()
        print(f"Recuperati {record['recovered'] if record else 0} interventi orfani via name-matching.")

    def load_all_roles(self):
        all_configs = [
            (GOVERNMENT_ROLES, 'governo'),
            (PARLIAMENT_ROLES, 'camera'),
            (CAPIGRUPPO, 'capogruppo'),
            (COMMISSION_ROLES, 'commissione')
        ]

        with self.driver.session() as session:
            self.clear_ruoli()
            
            # Step 1: Assign roles
            matched_count = 0
            not_found = []
            relationships_created = 0

            for role_dict, dict_type in all_configs:
                for nome, (ruolo_base, tipo_ruolo_cfg, target_entity) in role_dict.items():
                    
                    deputato_id = self.find_deputato(session, nome)
                    if not deputato_id:
                        not_found.append(nome)
                        continue

                    matched_count += 1
                    
                    if tipo_ruolo_cfg == 'capogruppo':
                        full_role_str = f"Presidente del Gruppo {target_entity}"
                        self.update_proprietà_ruolo(session, deputato_id, full_role_str, 'capogruppo', None)
                        if target_entity:
                            if self.create_relazione_gerarchica(session, deputato_id, target_entity, 'GruppoParlamentare', 'Presidente'):
                                relationships_created += 1
                    
                    elif tipo_ruolo_cfg == 'commissione':
                        full_role_str = f"{ruolo_base} {target_entity}"
                        self.update_proprietà_ruolo(session, deputato_id, full_role_str, 'commissione', target_entity)
                        if target_entity:
                            if self.create_relazione_gerarchica(session, deputato_id, target_entity, 'Commissione', ruolo_base):
                                relationships_created += 1
                            else:
                                short_name = target_entity.split('(')[0].strip()
                                if short_name != target_entity:
                                    if self.create_relazione_gerarchica(session, deputato_id, short_name, 'Commissione', ruolo_base):
                                        relationships_created += 1
                    
                    else:
                        self.update_proprietà_ruolo(session, deputato_id, ruolo_base, tipo_ruolo_cfg, target_entity)
                        if tipo_ruolo_cfg == 'governo' and target_entity:
                            if self.create_relazione_gerarchica(session, deputato_id, target_entity, 'Commissione', 'Riferimento Governo'):
                                relationships_created += 1

            # Step 2: Reconcile speeches (important for MembroGoverno without XML ID match)
            self.reconcile_orphan_interventions(session)

            print(f"\nRuoli elaborati: {matched_count}")
            print(f"Relazioni grafo create: {relationships_created}")
            
            if not_found:
                print(f"\nWARNING: Soggetti non trovati ({len(not_found)}):")
                for n in not_found[:10]:
                    print(f"  - {n}")

            # Stats finali
            res_types = session.run("""
                MATCH (d)
                WHERE d:Deputato OR d:MembroGoverno
                RETURN d.tipoRuolo as t, count(*) as c
                ORDER BY c DESC
            """)
            print("\nRiepilogo Ruoli (Proprietà):")
            for r in res_types:
                if r['t']: print(f"  {r['t']}: {r['c']}")

            res_rels = session.run("""
                MATCH ()-[r:È_PRESIDENTE|È_VICEPRESIDENTE|È_SEGRETARIO|RIFERIMENTO_GOVERNO]->()
                RETURN type(r) as t, count(*) as c
            """)
            print("\nRiepilogo Relazioni (Grafo):")
            for r in res_rels:
                print(f"  {r['t']}: {r['c']}")


def main():
    print("=" * 60)
    print("Caricamento Ruoli Istituzionali & Relazioni Graph - XIX Legislatura")
    print("=" * 60)
    
    loader = RuoliLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        loader.load_all_roles()
    finally:
        loader.close()
    
    print("\n" + "=" * 60)
    print("Operazione completata con successo.")
    print("=" * 60)


if __name__ == "__main__":
    main()
