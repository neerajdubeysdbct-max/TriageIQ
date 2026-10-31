# Backend API. Build from the repository root so the synthetic training data is included:
#   docker build -f backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    MLFLOW_DISABLE_AGENT_HINT=1 \
    HF_HOME=/app/cache/huggingface

WORKDIR /app/backend

# Pip downloads go to a BuildKit cache mount (not an image layer), so on a slow or flaky
# connection each retry, and each rebuild, resumes with the packages already fetched.
# PIP_INDEX_URL picks the package index (a closer PyPI mirror if pypi.org is slow);
# pip reads it from the environment.
ARG PIP_INDEX_URL=https://pypi.org/simple
# CPU-only torch first (the default wheel bundles CUDA and is several GB larger).
# --no-deps: torch's own dependencies come from PIP_INDEX_URL in the next step.
RUN --mount=type=cache,target=/root/.cache/pip \
    for i in 1 2 3 4 5; do \
        pip install --no-deps torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu && exit 0; \
        echo "pip install failed (attempt $i/5), retrying"; sleep 10; \
    done; exit 1
COPY backend/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    for i in 1 2 3 4 5; do \
        pip install -r requirements.txt && exit 0; \
        echo "pip install failed (attempt $i/5), retrying"; sleep 10; \
    done; exit 1

COPY sample_data/*.csv /app/sample_data/
COPY backend/ .
RUN chmod +x docker-entrypoint.sh \
    && useradd --create-home --uid 1000 app \
    && mkdir -p models reports outputs uploads /app/cache \
    && chown -R app:app /app

USER app
ENV BASE_TRAINING_TICKETS=/app/sample_data/northwind_incidents.csv \
    BASE_TRAINING_LABELS=/app/sample_data/northwind_ground_truth.csv

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
ENTRYPOINT ["./docker-entrypoint.sh"]