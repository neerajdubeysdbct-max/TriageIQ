"""
Indexing and hybrid retrieval of tickets.

Each ticket is one document: short description + closure notes (what happened and
how it was fixed). Documents are embedded with the same sentence-transformer the
clustering uses, and searched two ways:
  vector   cosine similarity of embeddings: finds tickets that mean the same thing
           in different words ("VPN keeps dropping" ~ "remote users disconnected")
  keyword  Postgres full-text search: exact terms, host names, error codes
The two rankings are merged with reciprocal rank fusion (RRF), which needs no
score calibration between the two methods.
"""

import time
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import text

from models import SessionLocal, Ticket
from services.rag.vector_store import get_store

RRF_K = 60                      # standard RRF constant; damps the weight of top ranks
CANDIDATES_PER_METHOD = 50
DOC_CHARS = 600                 # characters of each document that are embedded

FTS_EXPR = ("to_tsvector('english', coalesce(short_description, '') || ' ' || coalesce(close_notes, '') "
            "|| ' ' || coalesce(resolution_notes, ''))")


def document_text(short_description: Optional[str], close_notes: Optional[str]) -> str:
    return f"{short_description or ''}. {close_notes or ''}".strip()[:DOC_CHARS]


def _encoder():
    from services.ml_models import bert_clustering
    return bert_clustering.load_model()


def embed(texts: List[str]) -> np.ndarray:
    return np.asarray(_encoder().model.encode(texts, batch_size=256, show_progress_bar=False,
                                              convert_to_numpy=True, normalize_embeddings=True), dtype=np.float32)


def index_upload(upload_id: int) -> Dict:
    """Embed every ticket of an upload and store the vectors."""
    started = time.time()
    db = SessionLocal()
    try:
        rows = db.query(Ticket.id, Ticket.short_description, Ticket.close_notes, Ticket.resolution_notes) \
            .filter(Ticket.upload_id == upload_id).order_by(Ticket.id).all()
    finally:
        db.close()
    if not rows:
        return {"upload_id": upload_id, "indexed": 0}
    docs = [document_text(r.short_description, r.close_notes or r.resolution_notes) for r in rows]
    get_store().save(upload_id, [r.id for r in rows], embed(docs))
    summary = {"upload_id": upload_id, "indexed": len(rows), "seconds": round(time.time() - started, 1)}
    print(f"RAG index built for upload {upload_id}: {summary['indexed']:,} tickets in {summary['seconds']}s")
    return summary


def vector_search(upload_id: int, query: str, k: int = CANDIDATES_PER_METHOD) -> List[int]:
    return [tid for tid, _ in get_store().search(upload_id, embed([query])[0], k)]


def keyword_search(upload_id: int, query: str, k: int = CANDIDATES_PER_METHOD) -> List[int]:
    db = SessionLocal()
    try:
        rows = db.execute(text(f"""
            SELECT id FROM tickets
            WHERE upload_id = :u AND {FTS_EXPR} @@ websearch_to_tsquery('english', :q)
            ORDER BY ts_rank({FTS_EXPR}, websearch_to_tsquery('english', :q)) DESC
            LIMIT :k"""), {"u": upload_id, "q": query, "k": k}).fetchall()
        if not rows:
            # websearch syntax ANDs every term; fall back to OR so long questions still match
            terms = " | ".join(w for w in "".join(c if c.isalnum() else " " for c in query).split() if len(w) > 2)
            if terms:
                rows = db.execute(text(f"""
                    SELECT id FROM tickets
                    WHERE upload_id = :u AND {FTS_EXPR} @@ to_tsquery('english', :q)
                    ORDER BY ts_rank({FTS_EXPR}, to_tsquery('english', :q)) DESC
                    LIMIT :k"""), {"u": upload_id, "q": terms, "k": k}).fetchall()
        return [r.id for r in rows]
    finally:
        db.close()


def rrf(rankings: List[List[int]], k: int = RRF_K) -> List[tuple]:
    scores: Dict[int, float] = {}
    for ranking in rankings:
        for rank, tid in enumerate(ranking):
            scores[tid] = scores.get(tid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: -kv[1])


def search(upload_id: int, query: str, k: int = 8, method: str = "hybrid") -> List[Dict]:
    """Top-k tickets for a query. method: hybrid | vector | keyword."""
    if method == "vector":
        ranked = [(tid, None) for tid in vector_search(upload_id, query)]
    elif method == "keyword":
        ranked = [(tid, None) for tid in keyword_search(upload_id, query)]
    else:
        ranked = rrf([vector_search(upload_id, query), keyword_search(upload_id, query)])
    ids = [tid for tid, _ in ranked[:k]]
    if not ids:
        return []
    db = SessionLocal()
    try:
        tickets = {t.id: t for t in db.query(Ticket).filter(Ticket.id.in_(ids)).all()}
    finally:
        db.close()
    out = []
    for tid, score in ranked[:k]:
        t = tickets.get(tid)
        if t is None:
            continue
        out.append({
            "id": t.id, "number": t.ticket_number, "short_description": t.short_description,
            "close_notes": t.close_notes or t.resolution_notes, "assignment_group": t.assignment_group,
            "priority": t.priority, "resolved_by": t.resolved_by,
            "mttr_hours": round(t.mttr_hours, 2) if t.mttr_hours else None,
            "automation_status": t.aiops_automation_status, "category": t.l2_subcategory or t.category,
            "opened": t.opened.isoformat() if t.opened else None,
            "score": round(score, 4) if score is not None else None,
        })
    return out


def similar_tickets(upload_id: int, ticket_id: int, k: int = 5) -> List[Dict]:
    db = SessionLocal()
    try:
        t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.upload_id == upload_id).first()
    finally:
        db.close()
    if t is None:
        return []
    results = search(upload_id, document_text(t.short_description, t.close_notes or t.resolution_notes),
                     k=k + 1, method="vector")
    return [r for r in results if r["id"] != ticket_id][:k]
