from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth import decode_access_token

# Security scheme
security = HTTPBearer()


def _user_from_token(token: str) -> dict:
    user = decode_access_token(token)
    if not user.get("user_id") or not user.get("team_id"):
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to get current user from JWT token
    Returns: {"user_id": "john123", "team_id": "team_a"}
    """
    return _user_from_token(credentials.credentials)


def get_user_from_query_token(token: str = Query(..., description="JWT, for links opened directly by the browser")) -> dict:
    """Same as get_current_user, for download links that can't send an Authorization header."""
    return _user_from_token(token)


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """403 unless the caller's account has the admin role (checked in the database, not the token)."""
    from models import SessionLocal, User
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == user["user_id"]).first()
    finally:
        db.close()
    if not u or (u.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def check_upload_owner(upload_id: int, user: dict) -> dict:
    """404 unless the upload exists and belongs to the caller's team (no existence leak)."""
    from models import SessionLocal, Upload
    db = SessionLocal()
    try:
        owned = db.query(Upload.id).filter(Upload.id == upload_id, Upload.team_id == user["team_id"]).first()
    finally:
        db.close()
    if not owned:
        raise HTTPException(status_code=404, detail="Upload not found")
    return user


def require_upload_access(upload_id: int, user: dict = Depends(get_current_user)) -> dict:
    """
    Authorisation at the upload boundary: every endpoint that takes an
    upload_id uses this instead of get_current_user, so ticket queries can't
    reach another team's data even if they forget to filter by team.
    """
    return check_upload_owner(upload_id, user)


def require_upload_access_query_token(upload_id: int = Query(...),
                                      user: dict = Depends(get_user_from_query_token)) -> dict:
    """require_upload_access for browser download links (?upload_id=..&token=..)."""
    return check_upload_owner(upload_id, user)
