"""
Graph/metadata retrieval channel.

This channel leverages parliamentary structure (acts, committees, party affiliations)
to find relevant evidence through graph traversal.

Uses hybrid Eurovoc matching: lexical + semantic on existing embeddings.
NO new vector index required.
"""
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

import numpy as np

from ..neo4j_client import Neo4jClient
from ...models.evidence import compute_quote_text
from ...config import get_config

logger = logging.getLogger(__name__)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))


class GraphChannel:
    """
    Graph/metadata retrieval channel.

    Finds evidence through:
    1. Hybrid Eurovoc matching (lexical + semantic)
    2. Graph traversal: Act -> Firmatario -> Intervento -> Chunk
    3. Temporal filtering

    Uses existing embeddings (embedding_titolo, embedding_eurovoc) on AttoParlamentare.
    NO new vector index required.
    """

    def __init__(self, neo4j_client: Neo4jClient):
        """
        Initialize the graph retrieval channel.

        Args:
            neo4j_client: Neo4j database client
        """
        self.client = neo4j_client
        self.config = get_config()

    def extract_keywords(self, query: str) -> List[str]:
        """
        Extract keywords from a query for lexical matching.

        Simple keyword extraction - can be enhanced with NLP.
        """
        # Remove common Italian stopwords
        stopwords = {
            "il", "la", "lo", "i", "gli", "le", "un", "una", "uno",
            "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
            "e", "o", "ma", "che", "chi", "cui", "quale", "quali",
            "come", "dove", "quando", "perché", "quanto",
            "è", "sono", "essere", "stato", "stata", "stati", "state",
            "ha", "hanno", "avere", "aveva", "avevano",
            "qual", "cosa", "posizione", "partiti", "partito"
        }

        # Tokenize and filter
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]

        # Also include bigrams for compound terms
        bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)
                   if words[i] not in stopwords and words[i+1] not in stopwords]

        return keywords + bigrams[:5]  # Limit bigrams

    def retrieve(
        self,
        query: str,
        query_embedding: List[float],
        top_k: Optional[int] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve evidence through graph traversal.

        Strategy:
        1. Find relevant AttoParlamentare via hybrid matching
        2. Get signatories (PRIMO_FIRMATARIO, ALTRO_FIRMATARIO)
        3. Traverse to their interventions and chunks

        Args:
            query: User query text
            query_embedding: Query embedding vector
            top_k: Number of results to return
            date_start: Optional start date filter
            date_end: Optional end date filter

        Returns:
            List of evidence candidates
        """
        graph_config = self.config.retrieval.get("graph_channel", {})
        top_k = top_k or graph_config.get("max_acts_per_query", 100)

        keywords = self.extract_keywords(query)
        logger.info(f"Graph channel: keywords = {keywords}")

        if not keywords:
            logger.warning("No keywords extracted, skipping graph channel")
            return []

        # Step 1: Find relevant acts via lexical matching
        relevant_acts = self._find_relevant_acts(keywords, top_k=top_k)

        if not relevant_acts:
            logger.info("No relevant acts found via lexical search")
            return []

        # Step 2: Semantic rerank using embeddings
        reranked_acts = self._semantic_rerank(relevant_acts, query_embedding)

        # Step 3: Get chunks from signatories
        act_uris = [act["uri"] for act in reranked_acts[:50]]  # Limit
        chunks = self._get_chunks_from_signatories(
            act_uris,
            date_start=date_start,
            date_end=date_end
        )

        logger.info(f"Graph channel: retrieved {len(chunks)} chunks from {len(act_uris)} acts")
        return chunks

    def _find_relevant_acts(
        self,
        keywords: List[str],
        top_k: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Find relevant AttoParlamentare via lexical matching.

        Matches against eurovoc, titolo, and descrizione fields.
        """
        # Build OR conditions for keywords
        conditions = []
        params = {}
        for i, kw in enumerate(keywords):
            param_name = f"kw{i}"
            params[param_name] = kw.lower()
            conditions.append(f"""
                toLower(a.eurovoc) CONTAINS ${param_name} OR
                toLower(a.titolo) CONTAINS ${param_name} OR
                toLower(a.descrizione) CONTAINS ${param_name}
            """)

        where_clause = " OR ".join(conditions)

        cypher = f"""
        MATCH (a:AttoParlamentare)
        WHERE {where_clause}
        RETURN a.uri AS uri,
               a.titolo AS titolo,
               a.descrizione AS descrizione,
               a.eurovoc AS eurovoc,
               a.dataPresentazione AS data,
               a.tipo AS tipo,
               a.embedding_titolo AS embedding_titolo,
               a.embedding_eurovoc AS embedding_eurovoc
        LIMIT {top_k}
        """

        return self.client.query(cypher, params)

    def _semantic_rerank(
        self,
        acts: List[Dict[str, Any]],
        query_embedding: List[float]
    ) -> List[Dict[str, Any]]:
        """
        Rerank acts using semantic similarity with embeddings.

        Uses embedding_titolo if available, else default score.
        """
        threshold = self.config.retrieval.get("graph_channel", {}).get(
            "semantic_similarity_threshold", 0.4
        )

        scored_acts = []
        for act in acts:
            emb_titolo = act.get("embedding_titolo")
            emb_eurovoc = act.get("embedding_eurovoc")

            # Compute similarity with available embeddings
            similarities = []
            if emb_titolo and len(emb_titolo) == len(query_embedding):
                similarities.append(cosine_similarity(query_embedding, emb_titolo))
            if emb_eurovoc and len(emb_eurovoc) == len(query_embedding):
                similarities.append(cosine_similarity(query_embedding, emb_eurovoc))

            if similarities:
                act["similarity"] = max(similarities)
            else:
                act["similarity"] = 0.5  # Default for missing embeddings

            if act["similarity"] >= threshold:
                scored_acts.append(act)

        return sorted(scored_acts, key=lambda x: x["similarity"], reverse=True)

    def _get_chunks_from_signatories(
        self,
        act_uris: List[str],
        date_start: Optional[str] = None,
        date_end: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get chunks from interventions by act signatories.

        Traverses: Act <- FIRMATARIO - Deputato -> PRONUNCIATO_DA <- Intervento -> Chunk
        """
        if not act_uris:
            return []

        # Build date filter
        date_conditions = []
        params = {"act_uris": act_uris}

        if date_start:
            date_conditions.append("s.data >= $date_start")
            params["date_start"] = date_start
        if date_end:
            date_conditions.append("s.data <= $date_end")
            params["date_end"] = date_end

        date_clause = " AND ".join(date_conditions) if date_conditions else "1=1"

        cypher = f"""
        MATCH (speaker)-[:PRIMO_FIRMATARIO|ALTRO_FIRMATARIO]->(a:AttoParlamentare)
        WHERE a.uri IN $act_uris
        WITH DISTINCT speaker
        MATCH (i:Intervento)-[:PRONUNCIATO_DA]->(speaker)
        MATCH (i)-[:HA_CHUNK]->(c:Chunk)
        MATCH (i)<-[:CONTIENE_INTERVENTO]-(f:Fase)<-[:HA_FASE]-(d:Dibattito)<-[:HA_DIBATTITO]-(s:Seduta)
        WHERE {date_clause}
        OPTIONAL MATCH (speaker)-[mg:MEMBRO_GRUPPO]->(g:GruppoParlamentare)
        WHERE mg.dataInizio <= s.data AND (mg.dataFine IS NULL OR mg.dataFine >= s.data)
        RETURN c.id AS chunk_id,
               c.testo AS chunk_text,
               c.embedding AS embedding,
               c.start_char_raw AS span_start,
               c.end_char_raw AS span_end,
               i.id AS intervento_id,
               i.testo_raw AS testo_raw,
               speaker.id AS speaker_id,
               speaker.nome AS speaker_nome,
               speaker.cognome AS speaker_cognome,
               labels(speaker)[0] AS speaker_type,
               g.nome AS party,
               s.id AS seduta_id,
               s.data AS seduta_date,
               s.numero AS seduta_numero,
               d.titolo AS dibattito_titolo
        LIMIT 200
        """

        results = self.client.query(cypher, params)
        return self._process_results(results)

    def _process_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process raw results into evidence format."""
        processed = []
        config = get_config()

        for row in results:
            try:
                testo_raw = row.get("testo_raw", "")
                span_start = row.get("span_start", 0)
                span_end = row.get("span_end", 0)

                if testo_raw and span_start is not None and span_end is not None:
                    quote_text = compute_quote_text(testo_raw, span_start, span_end)
                else:
                    quote_text = row.get("chunk_text", "")

                party = row.get("party", "MISTO")
                coalition = config.get_coalition(party) if party else "opposizione"

                seduta_date = row.get("seduta_date", "")
                try:
                    date_obj = datetime.strptime(seduta_date, "%d/%m/%Y").date()
                except ValueError:
                    date_obj = datetime.now().date()

                processed.append({
                    "evidence_id": row.get("chunk_id", ""),
                    "doc_id": row.get("seduta_id", ""),
                    "speech_id": row.get("intervento_id", ""),
                    "speaker_id": row.get("speaker_id", ""),
                    "speaker_name": f"{row.get('speaker_nome', '')} {row.get('speaker_cognome', '')}".strip(),
                    "speaker_role": row.get("speaker_type", "Deputato"),
                    "party": party or "MISTO",
                    "coalition": coalition,
                    "date": date_obj,
                    "chunk_text": row.get("chunk_text", ""),
                    "quote_text": quote_text,
                    "span_start": span_start or 0,
                    "span_end": span_end or 0,
                    "dibattito_titolo": row.get("dibattito_titolo"),
                    "seduta_numero": row.get("seduta_numero", 0),
                    "similarity": 0.5,  # Default for graph channel
                    "embedding": row.get("embedding"),  # For compass PCA
                    "retrieval_channel": "graph"
                })
            except Exception as e:
                logger.error(f"Error processing graph result: {e}")
                continue

        return processed
