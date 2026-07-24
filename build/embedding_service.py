"""
Minimal embedding service for scripts. Reads config from environment variables.
Includes SQLite caching and batching.
"""
import os
import time
import hashlib
import sqlite3
import logging
from typing import Dict, List, Optional
import numpy as np
from openai import OpenAI

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")


class SQLiteCache:
    """Persistent cache based on SQLite."""

    def __init__(self, db_path: str = "embeddings_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    key TEXT PRIMARY KEY,
                    vector BLOB,
                    created_at REAL
                )
            """)
            conn.commit()

    def get(self, key: str) -> Optional[np.ndarray]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT vector FROM embeddings WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return np.frombuffer(row[0], dtype=np.float32)
        except Exception as e:
            logger.error(f"Cache read error: {e}")
        return None

    def set(self, key: str, vector: np.ndarray):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (key, vector, created_at) VALUES (?, ?, ?)",
                    (key, vector.astype(np.float32).tobytes(), time.time())
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    def set_many(self, items: List[tuple]):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO embeddings (key, vector, created_at) VALUES (?, ?, ?)",
                    [(k, v.astype(np.float32).tobytes(), time.time()) for k, v in items]
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Cache batch write error: {e}")


class EmbeddingService:
    """Embedding service with caching and batching."""

    def __init__(self, cache_path: Optional[str] = None):
        self._client = OpenAI(api_key=OPENAI_API_KEY)
        if cache_path is None:
            cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embeddings_cache.db")
        self._cache = SQLiteCache(cache_path)
        self._mem_cache: Dict[str, np.ndarray] = {}

    def _get_cache_key(self, text: str) -> str:
        normalized_text = " ".join(text.strip().split())
        key_content = f"{EMBEDDING_MODEL}\n{normalized_text}"
        return hashlib.sha256(key_content.encode('utf-8')).hexdigest()

    def get_embedding(self, text: str) -> np.ndarray:
        results = self.embed_texts([text])
        return results[0] if results else np.zeros(1536)

    def embed_texts(self, texts: List[str], batch_size: int = 256) -> List[np.ndarray]:
        if not texts:
            return []

        results: Dict[int, np.ndarray] = {}
        missing_indices: List[int] = []
        missing_texts: List[str] = []

        for i, text in enumerate(texts):
            if not text or not text.strip():
                results[i] = np.zeros(1536)
                continue

            cache_key = self._get_cache_key(text)

            if cache_key in self._mem_cache:
                results[i] = self._mem_cache[cache_key]
                continue

            cached_vec = self._cache.get(cache_key)
            if cached_vec is not None:
                self._mem_cache[cache_key] = cached_vec
                results[i] = cached_vec
            else:
                missing_indices.append(i)
                missing_texts.append(text)

        if missing_texts:
            total_items = len(missing_texts)
            n_batches = (total_items + batch_size - 1) // batch_size
            logger.info(f"[EMBEDDING] {total_items} new embeddings needed ({n_batches} batches)")

            start_time = time.time()

            for i in range(0, total_items, batch_size):
                batch_idx = (i // batch_size) + 1
                batch = missing_texts[i:i + batch_size]
                batch_indices = missing_indices[i:i + batch_size]

                try:
                    batch_start = time.time()
                    embeddings = self._call_openai_with_retry(batch)
                    batch_duration = time.time() - batch_start

                    updates = []
                    for j, emb_vec in enumerate(embeddings):
                        original_idx = batch_indices[j]
                        text = batch[j]
                        cache_key = self._get_cache_key(text)
                        vec_np = np.array(emb_vec)
                        results[original_idx] = vec_np
                        self._mem_cache[cache_key] = vec_np
                        updates.append((cache_key, vec_np))

                    self._cache.set_many(updates)

                    elapsed = time.time() - start_time
                    avg_time_per_batch = elapsed / batch_idx
                    remaining_batches = n_batches - batch_idx
                    eta_seconds = avg_time_per_batch * remaining_batches

                    if remaining_batches > 0:
                        logger.info(f"[EMBEDDING] Progress: {batch_idx}/{n_batches}. Time/batch: {batch_duration:.2f}s. ETA: {eta_seconds:.1f}s")
                    else:
                        logger.info(f"[EMBEDDING] All {n_batches} batches done in {elapsed:.1f}s")

                except Exception as e:
                    logger.error(f"[EMBEDDING] Batch {batch_idx} failed: {e}")
                    for idx in batch_indices:
                        results[idx] = np.zeros(1536)

        return [results.get(i, np.zeros(1536)) for i in range(len(texts))]

    def _call_openai_with_retry(self, texts: List[str], max_retries: int = 3) -> List[List[float]]:
        base_delay = 1

        safe_texts = []
        for t in texts:
            if len(t) > 20000:
                logger.warning(f"[EMBEDDING] Text truncated from {len(t)} to 20000 chars")
                safe_texts.append(t[:20000])
            else:
                safe_texts.append(t)

        for attempt in range(max_retries):
            try:
                response = self._client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=safe_texts
                )
                return [d.embedding for d in response.data]
            except Exception as e:
                is_transient = "429" in str(e) or "500" in str(e) or "503" in str(e)
                if is_transient and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[EMBEDDING] API Error {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    raise e
        return []
