"""
Choose the number of KMeans clusters from the data instead of a fixed k.

Embeddings are L2-normalised first, so Euclidean KMeans is equivalent to
clustering by cosine similarity (what sentence embeddings are built for).
k is the silhouette-best value within a range an operations team can act on
(10-30 groups). Silhouette alone keeps rising with k on templated ticket text
(near-duplicate descriptions reward ever-smaller clusters), so the range is
bounded; see reports/clustering_report.json for the sweep against ground truth.
"""

from typing import Dict, List

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

CANDIDATE_KS = [10, 12, 14, 16, 18, 20, 22, 25, 28, 30]
SELECTION_SAMPLE = 5000     # tickets used to compare k values on large uploads
SILHOUETTE_SAMPLE = 3000


def normalize_rows(emb: np.ndarray) -> np.ndarray:
    emb = np.asarray(emb, dtype=np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    return emb / np.where(norms == 0, 1, norms)


def kmeans_sweep(embeddings: np.ndarray, candidates: List[int] = CANDIDATE_KS, seed: int = 42) -> Dict:
    """Fit KMeans for each candidate k on (a sample of) the data; silhouette per k and the best k."""
    X = normalize_rows(embeddings)
    rng = np.random.default_rng(seed)
    if len(X) > SELECTION_SAMPLE:
        X = X[rng.choice(len(X), size=SELECTION_SAMPLE, replace=False)]
    sil_idx = rng.choice(len(X), size=min(len(X), SILHOUETTE_SAMPLE), replace=False)
    by_k = {}
    for k in [k for k in candidates if k < len(X) // 5]:
        km = KMeans(n_clusters=k, random_state=seed, n_init=5).fit(X)
        by_k[k] = {"labels": km.labels_,
                   "silhouette": round(float(silhouette_score(X[sil_idx], km.labels_[sil_idx])), 4)}
    if not by_k:  # very small upload
        return {"by_k": {}, "best_k": max(2, len(X) // 10), "normalized": X}
    best_k = max(by_k, key=lambda k: by_k[k]["silhouette"])
    return {"by_k": by_k, "best_k": best_k, "normalized": X}


def choose_k(embeddings: np.ndarray) -> Dict:
    """What the pipeline stores per upload: chosen k and the silhouette of every candidate."""
    sweep = kmeans_sweep(embeddings)
    return {"chosen_k": sweep["best_k"], "method": "max silhouette within 10-30 clusters",
            "silhouette_by_k": {str(k): v["silhouette"] for k, v in sweep["by_k"].items()}}
