# TriageIQ

Ticket analytics for IT service desks. Upload a ServiceNow-style export (incidents, requests, changes or problems)
and TriageIQ tells you which tickets are already automated, which could be, what the recurring themes are, where
SLAs break, which tickets are anomalous, and answers questions about the data with cited evidence.

Everything runs on your own infrastructure, including the language model (Ollama), so ticket data never leaves it.

## What is in it

| Capability | How | Evaluated against |
|---|---|---|
| Automation status (Already / Can Be / Manual) | XGBoost on TF-IDF + ticket metadata, isotonic calibration, SHAP explanations | Majority class, "resolved by a bot" rule, logistic regression |
| Category routing at creation time | Logistic regression on word and character n-grams of the description | Keyword rules, the ticket's own category field |
| Ticket themes | MiniLM sentence embeddings + KMeans, k chosen by silhouette | Adjusted Rand index against true subcategories |
| Anomalies | IsolationForest on features relative to each ticket type | Planted anomalies (average precision) |
| Volume forecast | Backtested model selection with a parsimony rule | Seasonal naive, weekday mean, ridge, LSTM |
| Copilot | Planner + whitelisted SQL tool + hybrid retrieval (vector + full text, RRF) + citation and number verification | Answer key, previous copilot |
| Learning loop | Review queue, retraining with a frozen gold set and promotion gate, drift monitoring, MLflow registry, rollback | Accuracy on a second customer before and after labelling |

## Results

Models are trained and evaluated on synthetic data with known ground truth (real customer dumps can't be published;
see [Data](#data)). Full details, protocols and limitations: [docs/MODEL_CARD.md](docs/MODEL_CARD.md).

| | Result | Baseline |
|---|---|---|
| Automation status, held-out test | 95.0% accuracy, macro F1 0.950 | bot-resolver rule 70.2%, F1 0.575 |
| Automation status, unseen dump through the app | 95.6% | 66.4% (previous rule-based scorer) |
| Category routing, L1 / L2 | 93.7% / 92.0% | ticket's own category field 70.3% / 76.3% |
| Anomalies, average precision (base rate 2.5%) | 0.75 | previous rule score 0.32 |
| New customer, before and after 300 analyst labels | 73.1% → 92.6% | |
| Copilot, numeric questions (15) | 100% | previous copilot 53% |
| Copilot retrieval, precision@8 | hybrid 0.953 | vector 0.906, keyword 0.867 |

Some honest notes from the model card: logistic regression matches XGBoost on the automation task; the forecast
picks its model per upload and the LSTM is only within noise of a weekday mean (chosen on the unseen dump, the LSTM on
the training dump); the copilot's question set is small and written by the
author, so it is a regression suite rather than a benchmark.

## Architecture

```mermaid
flowchart LR
    U[Browser<br/>Next.js dashboard] -->|JWT| API[FastAPI]
    API --> PG[(Postgres<br/>tickets, labels,<br/>pgvector embeddings)]
    API --> M[Models<br/>XGBoost, LR, IsolationForest,<br/>MiniLM embeddings]
    API --> LLM[Ollama<br/>Qwen 2.5 7B, local]
    API --> ML[MLflow<br/>runs and model versions]
    subgraph Upload pipeline
      P1[Parse and detect dump type] --> P2[Embed and cluster] --> P3[Categorise] --> P4[Score automation<br/>+ drift check] --> P5[Index for search]
    end
    API --> P1
```

Copilot, per question:

```
question → planner (LLM, JSON schema; invalid plan is repaired once)
         → entity linking in code (team, channel, resolver, priority named in the question)
         → numbers: whitelisted aggregate tool (no LLM-written SQL)   explanations: hybrid search, top 8
         → answer from that evidence only, with ticket citations
         → verify: citations must be retrieved tickets; numbers must exist in the evidence;
           rewrite once, otherwise withhold the answer
```

## Run it

### Docker

```bash
cp .env.example .env            # set POSTGRES_PASSWORD, TRIAGEIQ_SECRET_KEY, ADMIN_PASSWORD
ollama pull qwen2.5:7b          # the LLM runs on the host
docker compose up --build
```

Open http://localhost:3000 and sign in with the admin account from `.env`. On first start the backend trains its
models on the bundled synthetic data (about a minute). Upload `sample_data/northwind_q3_incidents.csv` to see the
full pipeline. API documentation: http://localhost:8000/docs.

### Local development

Requires Python 3.12, Node 20, Postgres 16 and Ollama.

```bash
cd backend
python -m venv venv && venv/bin/pip install -r requirements-dev.txt
echo "DATABASE_URL=postgresql://user:pass@localhost:5432/triageiq" > .env
venv/bin/python migrate.py
venv/bin/python train_automation_model.py --tickets ../sample_data/northwind_incidents.csv --labels ../sample_data/northwind_ground_truth.csv
venv/bin/python train_category_model.py   --tickets ../sample_data/northwind_incidents.csv --labels ../sample_data/northwind_ground_truth.csv
ADMIN_USERNAME=admin ADMIN_PASSWORD=change-me-please venv/bin/python create_admin.py
venv/bin/uvicorn main:app --port 8000

cd ../frontend && npm ci && npm run dev
```

### Tests

```bash
cd backend && pytest
```

90 tests covering authentication and team isolation (every denied case is paired with an allowed one), the shared
metric definitions (MTTR and savings must match across pages), the copilot's query validation, entity linking,
verification and fail-closed behaviour (with a mocked LLM), and the monitoring statistics (PSI, Wilson interval).
They create their own data and remove it afterwards. CI also retrains the classifier and fails if test macro F1
drops below 0.93.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Postgres connection | `postgresql://postgres:postgres@localhost:5432/triageiq` |
| `TRIAGEIQ_SECRET_KEY` | JWT signing key | generated once into `backend/.secret_key` |
| `OLLAMA_URL`, `LLM_MODEL` | Local LLM | `http://localhost:11434`, `qwen2.5:7b` |
| `VECTOR_STORE` | `numpy` (exact search, files) or `pgvector` (HNSW in Postgres) | `numpy`; `pgvector` in Docker |
| `CORS_ORIGINS` | Dashboard origins allowed to call the API | `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | API address used by the browser (build time) | `http://localhost:8000` |

## Data

`sample_data/generate_synthetic_tickets.py` creates ServiceNow-style dumps for fictional companies with the problems
real exports have: vague descriptions, wrong category fields, misrouted tickets, useless closure notes, label noise
and planted anomalies. Each dump comes with a ground-truth file that is never uploaded, so every model can be scored.
A second customer profile (`--profile contoso`) uses different team names, bot accounts and wording, to test drift
and retraining.

No customer data is included in this repository, and uploads, outputs and model files are excluded by `.gitignore`.

## Repository layout

```
backend/
  main.py, routers/        API (auth, uploads, dashboards, review queue, model admin, copilot)
  ml/                      model definitions (automation, category, anomaly, forecast)
  services/                pipeline steps, drift, model lifecycle, shared metrics, rag/
  migrations/, migrate.py  schema changes, applied idempotently
  train_*.py, evaluate_*.py, experiments/   training, evaluation, experiments
  reports/                 evaluation outputs referenced by the model card
  tests/
frontend/app/dashboard/    Next.js dashboard
sample_data/               synthetic data generator and datasets
docs/                      model card and teaching notes
```

## Teaching notes

[docs/teaching](docs/teaching) walks through the ML engineering behind the project, with concepts, interview
questions and graded exercises: the learning loop (labels, drift, evaluation gates) and retrieval-augmented
generation so far.
