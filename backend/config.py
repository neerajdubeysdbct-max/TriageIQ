"""
Runtime configuration from environment variables (or backend/.env).

Secrets never live in code:
  TRIAGEIQ_SECRET_KEY  JWT signing key. If unset, a random key is generated
                         once into backend/.secret_key (git-ignored).
  DATABASE_URL           Postgres connection string.
"""

import os
import secrets

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path: str):
    """Minimal KEY=VALUE reader; real environment variables take precedence."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _secret_key() -> str:
    key = os.environ.get("TRIAGEIQ_SECRET_KEY")
    if key:
        return key
    path = os.path.join(BACKEND_DIR, ".secret_key")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(secrets.token_urlsafe(48))
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


_load_dotenv(os.path.join(BACKEND_DIR, ".env"))

SECRET_KEY = _secret_key()
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/triageiq")

# Where ticket embeddings for the copilot are stored: numpy (files, exact search) or pgvector (HNSW)
VECTOR_STORE = os.environ.get("VECTOR_STORE", "numpy").lower()

# Browser origins allowed to call the API (comma-separated)
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

# Local LLM (Ollama). Client ticket data is only ever sent to this URL.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:7b")

# Base labelled dataset for the automation classifier; analyst labels from the
# Review Queue are added to it on every retraining (services/model_lifecycle.py)
BASE_TRAINING_TICKETS = os.environ.get(
    "BASE_TRAINING_TICKETS", os.path.join(BACKEND_DIR, "..", "sample_data", "northwind_incidents.csv"))
BASE_TRAINING_LABELS = os.environ.get(
    "BASE_TRAINING_LABELS", os.path.join(BACKEND_DIR, "..", "sample_data", "northwind_ground_truth.csv"))
# Experiment tracking: local SQLite store, artifacts (model files) under backend/mlruns
MLFLOW_TRACKING_URI = os.environ.get(
    "MLFLOW_TRACKING_URI", "sqlite:///" + os.path.join(BACKEND_DIR, "mlflow.db").replace("\\", "/"))
MLFLOW_ARTIFACT_ROOT = os.environ.get("MLFLOW_ARTIFACT_ROOT", os.path.join(BACKEND_DIR, "mlruns"))
