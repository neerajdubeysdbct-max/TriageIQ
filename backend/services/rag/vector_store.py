"""
Vector store for ticket embeddings, behind a small interface so the backend can
be swapped without touching retrieval code.

  NumpyVectorStore  one matrix per upload on local disk, exact cosine search in
                    memory. Fine up to a few hundred thousand tickets per upload
                    (37k x 384 float32 = 57 MB, a search is a single matrix product).
  PgVectorStore     the same interface over a Postgres `vector(384)` column with an
                    HNSW index (pgvector). Vectors live next to the tickets, are backed
                    up with them and shared by every API worker. Needs the extension,
                    which the Docker Compose database image includes.

Selected with VECTOR_STORE=numpy|pgvector (config.py).
"""

import os
from collections import OrderedDict
from typing import List, Optional, Protocol, Sequence, Tuple

import numpy as np


class VectorStore(Protocol):
    def save(self, upload_id: int, ticket_ids: Sequence[int], vectors: np.ndarray) -> None: ...
    def search(self, upload_id: int, query: np.ndarray, k: int,
               allowed_ids: Optional[Sequence[int]] = None) -> List[Tuple[int, float]]: ...
    def exists(self, upload_id: int) -> bool: ...


class NumpyVectorStore:
    """Exact cosine search; vectors are L2-normalised when saved so a dot product is the cosine."""

    def __init__(self, root: str = "outputs", cache_size: int = 4):
        self.root = root
        self.cache: "OrderedDict[int, Tuple[np.ndarray, np.ndarray]]" = OrderedDict()
        self.cache_size = cache_size

    def _paths(self, upload_id: int):
        base = os.path.join(self.root, f"upload_{upload_id}")
        return os.path.join(base, "rag_vectors.npy"), os.path.join(base, "rag_ids.npy")

    def exists(self, upload_id: int) -> bool:
        return all(os.path.exists(p) for p in self._paths(upload_id))

    def save(self, upload_id: int, ticket_ids: Sequence[int], vectors: np.ndarray) -> None:
        vec_path, id_path = self._paths(upload_id)
        os.makedirs(os.path.dirname(vec_path), exist_ok=True)
        v = np.array(vectors, dtype=np.float32)          # copy: input may be read-only (memory-mapped)
        v /= np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-12, None)
        np.save(vec_path, v)
        np.save(id_path, np.asarray(ticket_ids, dtype=np.int64))
        self.cache.pop(upload_id, None)

    def _load(self, upload_id: int) -> Tuple[np.ndarray, np.ndarray]:
        if upload_id in self.cache:
            self.cache.move_to_end(upload_id)
            return self.cache[upload_id]
        vec_path, id_path = self._paths(upload_id)
        data = (np.load(vec_path, mmap_mode="r"), np.load(id_path))
        self.cache[upload_id] = data
        if len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
        return data

    def search(self, upload_id: int, query: np.ndarray, k: int,
               allowed_ids: Optional[Sequence[int]] = None) -> List[Tuple[int, float]]:
        vectors, ids = self._load(upload_id)
        q = np.array(query, dtype=np.float32).ravel()
        q /= max(float(np.linalg.norm(q)), 1e-12)
        scores = vectors @ q
        if allowed_ids is not None:
            mask = np.isin(ids, np.asarray(list(allowed_ids), dtype=np.int64))
            scores = np.where(mask, scores, -np.inf)
        k = min(k, int(np.isfinite(scores).sum()))
        if k <= 0:
            return []
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(ids[i]), float(scores[i])) for i in top]


class PgVectorStore:
    """
    Approximate nearest-neighbour search with an HNSW index (cosine distance).
    HNSW is approximate: recall against exact search should be measured
    (experiments/vector_store_benchmark.py) before relying on it.
    """

    def __init__(self, dim: int = 384, ef_search: int = 100):
        self.dim, self.ef_search = dim, ef_search
        self._ready = False

    def _engine(self):
        from models import engine
        if not self._ready:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS ticket_embeddings (
                        ticket_id BIGINT PRIMARY KEY,
                        upload_id INTEGER NOT NULL,
                        embedding vector({self.dim}) NOT NULL)"""))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ticket_embeddings_upload ON ticket_embeddings (upload_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ticket_embeddings_hnsw ON ticket_embeddings "
                                  "USING hnsw (embedding vector_cosine_ops)"))
            self._ready = True
        return engine

    @staticmethod
    def _literal(v: np.ndarray) -> str:
        return "[" + ",".join(f"{x:.6f}" for x in v) + "]"

    def exists(self, upload_id: int) -> bool:
        from sqlalchemy import text
        with self._engine().connect() as conn:
            return conn.execute(text("SELECT 1 FROM ticket_embeddings WHERE upload_id = :u LIMIT 1"),
                                {"u": upload_id}).first() is not None

    def save(self, upload_id: int, ticket_ids: Sequence[int], vectors: np.ndarray) -> None:
        from sqlalchemy import text
        v = np.array(vectors, dtype=np.float32)          # copy: input may be read-only (memory-mapped)
        v /= np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-12, None)
        insert = text("INSERT INTO ticket_embeddings (ticket_id, upload_id, embedding) "
                      "VALUES (:t, :u, CAST(:e AS vector))")
        with self._engine().begin() as conn:
            conn.execute(text("DELETE FROM ticket_embeddings WHERE upload_id = :u"), {"u": upload_id})
            for start in range(0, len(v), 2000):
                conn.execute(insert, [{"t": int(t), "u": upload_id, "e": self._literal(row)}
                                      for t, row in zip(ticket_ids[start:start + 2000], v[start:start + 2000])])

    def search(self, upload_id: int, query: np.ndarray, k: int,
               allowed_ids: Optional[Sequence[int]] = None) -> List[Tuple[int, float]]:
        from sqlalchemy import text
        q = np.array(query, dtype=np.float32).ravel()
        q /= max(float(np.linalg.norm(q)), 1e-12)
        where = "upload_id = :u" + (" AND ticket_id = ANY(:ids)" if allowed_ids is not None else "")
        params = {"u": upload_id, "q": self._literal(q), "k": k}
        if allowed_ids is not None:
            params["ids"] = [int(i) for i in allowed_ids]
        with self._engine().begin() as conn:
            conn.execute(text(f"SET LOCAL hnsw.ef_search = {int(self.ef_search)}"))
            # the index is shared by all uploads; iterative scans keep the upload filter from starving results
            conn.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
            rows = conn.execute(text(
                f"SELECT ticket_id, 1 - (embedding <=> CAST(:q AS vector)) AS score FROM ticket_embeddings "
                f"WHERE {where} ORDER BY embedding <=> CAST(:q AS vector) LIMIT :k"), params).all()
        return [(int(r.ticket_id), float(r.score)) for r in rows]


_store: Optional[VectorStore] = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        from config import VECTOR_STORE
        _store = PgVectorStore() if VECTOR_STORE == "pgvector" else NumpyVectorStore()
    return _store
