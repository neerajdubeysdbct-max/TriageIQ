"""
Exact search (NumpyVectorStore) vs approximate HNSW search (PgVectorStore).

Copies an upload's stored embeddings into pgvector, then uses random tickets'
own vectors as queries and measures:
  recall@k   share of the exact top-k that HNSW also returns
  tie-aware  share of HNSW results at least as similar as the exact k-th result
             (templated ticket text has many identical vectors, so plain recall
             counts an equally similar ticket as a miss)
  latency    per query, p50 / p95, for both stores

    DATABASE_URL=postgresql://...pgvector-db... python experiments/vector_store_benchmark.py --upload-id 5

Writes reports/vector_store_benchmark_<upload>.json.
"""

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.rag.vector_store import NumpyVectorStore, PgVectorStore  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload-id", type=int, required=True)
    ap.add_argument("--queries", type=int, default=200)
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--ef-search", type=int, default=100)
    args = ap.parse_args()

    exact = NumpyVectorStore()
    if not exact.exists(args.upload_id):
        sys.exit(f"upload {args.upload_id} has no numpy index; build it first")
    vectors, ids = exact._load(args.upload_id)
    vectors = np.asarray(vectors)

    approx = PgVectorStore(ef_search=args.ef_search)
    t = time.time()
    approx.save(args.upload_id, ids.tolist(), vectors)
    load_s = time.time() - t

    rng = np.random.default_rng(0)
    picks = rng.choice(len(ids), size=min(args.queries, len(ids)), replace=False)
    recalls, tie_aware, t_exact, t_approx = [], [], [], []
    for i in picks:
        q = vectors[i]
        t0 = time.perf_counter()
        exact_top = exact.search(args.upload_id, q, args.k)
        t1 = time.perf_counter()
        found = {tid for tid, _ in approx.search(args.upload_id, q, args.k)}
        t2 = time.perf_counter()
        truth = {tid for tid, _ in exact_top}
        recalls.append(len(truth & found) / len(truth))
        kth = exact_top[-1][1]
        sims = dict(zip(ids.tolist(), (vectors @ (q / np.linalg.norm(q))).tolist()))
        tie_aware.append(sum(sims[t] >= kth - 1e-5 for t in found) / len(truth))
        t_exact.append((t1 - t0) * 1000)
        t_approx.append((t2 - t1) * 1000)

    report = {
        "upload_id": args.upload_id, "tickets": int(len(ids)), "dim": int(vectors.shape[1]),
        "queries": len(picks), "k": args.k, "ef_search": args.ef_search,
        "pgvector_load_seconds": round(load_s, 1),
        f"recall_at_{args.k}": round(float(np.mean(recalls)), 4),
        "queries_with_full_recall": round(float(np.mean([r == 1.0 for r in recalls])), 4),
        f"tie_aware_recall_at_{args.k}": round(float(np.mean(tie_aware)), 4),
        "exact_ms_p50": round(float(np.percentile(t_exact, 50)), 2), "exact_ms_p95": round(float(np.percentile(t_exact, 95)), 2),
        "hnsw_ms_p50": round(float(np.percentile(t_approx, 50)), 2), "hnsw_ms_p95": round(float(np.percentile(t_approx, 95)), 2),
        "note": "pgvector latency includes a database round trip; exact search is in-process",
    }
    print(json.dumps(report, indent=2))
    os.makedirs("reports", exist_ok=True)
    with open(f"reports/vector_store_benchmark_{args.upload_id}.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
