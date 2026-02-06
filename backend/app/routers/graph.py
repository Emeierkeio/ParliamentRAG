"""
Graph exploration endpoints for Neo4j schema and queries.
"""
import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.neo4j_client import Neo4jClient
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["Graph"])

# English labels (migrated schema)
ENGLISH_LABELS = {
    "Speech", "Phase", "Debate", "Session", "Deputy",
    "GovernmentMember", "ParliamentaryGroup", "Committee",
    "ParliamentaryAct", "Chunk"
}

# English relationship types (migrated schema)
ENGLISH_RELATIONSHIPS = {
    "SPOKEN_BY", "CONTAINS_SPEECH", "HAS_PHASE", "HAS_DEBATE",
    "HAS_CHUNK", "MEMBER_OF_GROUP", "MEMBER_OF_COMMITTEE",
    "PRIMARY_SIGNATORY", "CO_SIGNATORY", "IS_PRESIDENT",
    "IS_SECRETARY", "IS_VICE_PRESIDENT", "GOVERNMENT_REFERENCE", "NEXT"
}

# Global client instance
_neo4j_client: Optional[Neo4jClient] = None


def get_client() -> Neo4jClient:
    """Get or initialize Neo4j client."""
    global _neo4j_client
    if _neo4j_client is None:
        settings = get_settings()
        _neo4j_client = Neo4jClient(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )
    return _neo4j_client


def serialize_neo4j_value(value: Any) -> Any:
    """Serialize Neo4j types to JSON-compatible values."""
    if value is None:
        return None
    # Handle Neo4j Date/DateTime/Time
    if hasattr(value, 'iso_format'):
        return value.iso_format()
    # Handle Neo4j Duration
    if hasattr(value, 'months') and hasattr(value, 'days') and hasattr(value, 'seconds'):
        return str(value)
    # Handle lists
    if isinstance(value, list):
        return [serialize_neo4j_value(v) for v in value]
    # Handle dicts
    if isinstance(value, dict):
        return {k: serialize_neo4j_value(v) for k, v in value.items()}
    return value


class CypherQueryRequest(BaseModel):
    """Request model for Cypher queries."""
    cypher: str


@router.get("/schema")
async def get_graph_schema() -> Dict[str, Any]:
    """
    Get the Neo4j database schema.

    Returns node labels, relationship types, and their properties.
    """
    client = get_client()

    try:
        # Get node labels (filter to English only)
        with client.session() as session:
            labels_result = session.run("CALL db.labels()")
            all_labels = [record["label"] for record in labels_result]
            labels = [l for l in all_labels if l in ENGLISH_LABELS]

        # Get relationship types (filter to English only)
        with client.session() as session:
            rel_result = session.run("CALL db.relationshipTypes()")
            all_rels = [record["relationshipType"] for record in rel_result]
            relationship_types = [r for r in all_rels if r in ENGLISH_RELATIONSHIPS]

        # Get property keys
        with client.session() as session:
            props_result = session.run("CALL db.propertyKeys()")
            property_keys = [record["propertyKey"] for record in props_result]

        # Get sample properties per label
        node_schemas = {}
        for label in labels:  # Already filtered to English
            with client.session() as session:
                query = f"""
                MATCH (n:{label})
                WITH n LIMIT 1
                RETURN keys(n) AS properties
                """
                result = session.run(query)
                record = result.single()
                if record:
                    node_schemas[label] = {
                        "properties": record["properties"],
                        "sample_count": 1
                    }

        return {
            "labels": labels,
            "relationship_types": relationship_types,
            "property_keys": property_keys,
            "node_schemas": node_schemas,
        }

    except Exception as e:
        logger.error(f"Failed to get schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_graph_stats() -> Dict[str, Any]:
    """
    Get database statistics.

    Returns counts of nodes and relationships.
    """
    client = get_client()

    try:
        stats = {}

        # Get node counts by label (English only)
        with client.session() as session:
            labels_result = session.run("CALL db.labels()")
            all_labels = [record["label"] for record in labels_result]
            labels = [l for l in all_labels if l in ENGLISH_LABELS]

        node_counts = {}
        for label in labels:  # Already filtered to English
            with client.session() as session:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) AS count")
                record = result.single()
                if record:
                    node_counts[label] = record["count"]

        # Get total counts
        with client.session() as session:
            total_nodes = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]
            total_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"]

        return {
            "total_nodes": total_nodes,
            "total_relationships": total_rels,
            "node_counts": node_counts,
        }

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def execute_cypher_query(request: CypherQueryRequest) -> Dict[str, Any]:
    """
    Execute a read-only Cypher query.

    WARNING: Only read queries are allowed for safety.
    """
    client = get_client()
    cypher = request.cypher.strip()

    # Basic safety check - block write operations
    dangerous_keywords = [
        "CREATE", "DELETE", "DETACH", "SET", "REMOVE", "MERGE",
        "DROP", "CALL db.createIndex", "CALL db.createConstraint"
    ]

    cypher_upper = cypher.upper()
    for keyword in dangerous_keywords:
        if keyword in cypher_upper:
            raise HTTPException(
                status_code=400,
                detail=f"Write operations are not allowed: {keyword}"
            )

    try:
        with client.session() as session:
            result = session.run(cypher)
            records = []

            for record in result:
                # Convert record to dict, handling Neo4j types
                record_dict = {}
                for key in record.keys():
                    value = record[key]
                    # Handle Neo4j Node objects
                    if hasattr(value, 'labels'):
                        record_dict[key] = {
                            "id": value.element_id,
                            "labels": list(value.labels),
                            "properties": serialize_neo4j_value(dict(value))
                        }
                    # Handle Neo4j Relationship objects
                    elif hasattr(value, 'type'):
                        record_dict[key] = {
                            "type": value.type,
                            "properties": serialize_neo4j_value(dict(value))
                        }
                    else:
                        record_dict[key] = serialize_neo4j_value(value)
                records.append(record_dict)

            return {
                "records": records[:1000],  # Limit results
                "count": len(records),
                "truncated": len(records) > 1000
            }

    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
