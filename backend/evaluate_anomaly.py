"""
Score anomaly detection against planted anomalies (ground truth is_anomaly).

    python evaluate_anomaly.py

Runs on the training dump and the unseen Q3 dump. Compares:
  - global MTTR z-score (baseline)
  - the previous hand-weighted rule score (baseline)
  - IsolationForest without ticket-type context (ablation)
  - IsolationForest with ticket-type context (the model)
Metrics: average precision (area under precision-recall; base rate ~2.5%),
precision@k with k = number of true anomalies, and precision / recall of the
flagged set at the model's operating point. Writes reports/anomaly_report.json.
"""

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from ml.anomaly_model import build_features, global_mttr_z, legacy_rule_score, score
from utils import normalize_priority

DATASETS = {
    "train dump (northwind)": ("../sample_data/northwind_incidents.csv", "../sample_data/northwind_ground_truth.csv"),
    "unseen dump (northwind_q3)": ("../sample_data/northwind_q3_incidents.csv", "../sample_data/northwind_q3_ground_truth.csv"),
}


def load(tickets, labels):
    raw = pd.read_csv(tickets).merge(pd.read_csv(labels), on="number")
    opened = pd.to_datetime(raw["opened_at"])
    df = pd.DataFrame({
        "mttr_hours": (pd.to_datetime(raw["resolved_at"]) - opened).dt.total_seconds() / 3600,
        "reassignment_count": raw["reassignment_count"], "reopen_count": raw["reopen_count"],
        "opened": opened, "priority_level": raw["priority"].map(normalize_priority),
    })
    # Group = ticket type as the pipeline sees it: the category model's L2 prediction
    import joblib
    from ml.category_model import frame_for
    clf = joblib.load("models/category_classifier.joblib")["classifier"]
    df["group"] = clf.predict(frame_for(raw))["l2"].to_numpy()
    return df, raw


def at_k(y, s, k):
    top = np.argsort(-s)[:k]
    return float(y[top].mean())


def main():
    report = {"generated_at": datetime.now().isoformat(timespec="seconds"), "datasets": {}}
    for name, (tickets, labels) in DATASETS.items():
        df, raw = load(tickets, labels)
        y = raw["is_anomaly"].to_numpy()
        k = int(y.sum())
        ctx = score(build_features(df))
        flat = score(build_features(df.assign(group="all")))
        candidates = {
            "Global MTTR z-score": global_mttr_z(df),
            "Previous rule score": legacy_rule_score(df),
            "IsolationForest, no context": flat["anomaly_score"].to_numpy(),
            "IsolationForest, per ticket type": ctx["anomaly_score"].to_numpy(),
        }
        rows = [{"model": m, "average_precision": round(float(average_precision_score(y, s)), 4),
                 "precision_at_k": round(at_k(y, s, k), 4)} for m, s in candidates.items()]
        flagged = ctx["is_anomaly"].to_numpy()
        by_type = (raw.assign(caught=flagged).query("is_anomaly == 1")
                   .groupby("anomaly_type")["caught"].mean().round(4).to_dict())
        report["datasets"][name] = {
            "tickets": len(df), "true_anomalies": k, "base_rate": round(k / len(df), 4),
            "results": rows,
            "operating_point": {"flagged": int(flagged.sum()),
                                "precision": round(float(y[flagged].mean()), 4) if flagged.any() else None,
                                "recall": round(float(flagged[y == 1].mean()), 4)},
            "recall_by_anomaly_type": by_type,
        }
        print(f"\n{name}: {k} true anomalies of {len(df)} (base rate {k/len(df):.1%})")
        for r in rows:
            print(f"  {r['model']:34s} AP {r['average_precision']:.3f}   precision@{k} {r['precision_at_k']:.3f}")
        print("  operating point:", report["datasets"][name]["operating_point"], "| recall by type:", by_type)

    os.makedirs("reports", exist_ok=True)
    with open("reports/anomaly_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
