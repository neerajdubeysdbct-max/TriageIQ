"""
Copilot API backed by retrieval-augmented generation over the dataset's tickets
(services/rag). All endpoints check that the upload belongs to the caller's team.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from dependencies import check_upload_owner, get_current_user, require_upload_access

router = APIRouter(prefix="/api/rag", tags=["Copilot (RAG)"])


class AskRequest(BaseModel):
    upload_id: int
    question: str = Field(min_length=3, max_length=1000)


@router.post("/ask")
def ask(req: AskRequest, user: dict = Depends(get_current_user)):
    check_upload_owner(req.upload_id, user)
    from services.rag.answer import ask as run
    from services.rag.vector_store import get_store
    if not get_store().exists(req.upload_id):
        raise HTTPException(409, "This dataset has not been indexed for search yet")
    try:
        return run(req.upload_id, user["team_id"], req.question.strip())
    except Exception as e:  # LLM unreachable etc.
        raise HTTPException(503, f"Copilot unavailable: {e.__class__.__name__}")


@router.get("/status/{upload_id}")
def status(upload_id: int, user: dict = Depends(require_upload_access)):
    from services.rag.vector_store import get_store
    return {"indexed": get_store().exists(upload_id)}


@router.post("/index/{upload_id}")
def build_index(upload_id: int, background: BackgroundTasks, user: dict = Depends(require_upload_access)):
    from services.rag.retrieval import index_upload
    background.add_task(index_upload, upload_id)
    return {"state": "running"}


@router.get("/similar/{upload_id}/{ticket_id}")
def similar(upload_id: int, ticket_id: int, k: int = 5, user: dict = Depends(require_upload_access)):
    from services.rag.retrieval import similar_tickets
    from services.rag.vector_store import get_store
    if not get_store().exists(upload_id):
        return {"tickets": [], "indexed": False}
    return {"tickets": similar_tickets(upload_id, ticket_id, k=max(1, min(k, 20))), "indexed": True}
