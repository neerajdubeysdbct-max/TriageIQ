"""
Train and evaluate the L1 (tower) / L2 (subcategory) classifier.

    python train_category_model.py \
        --tickets ../sample_data/northwind_incidents.csv \
        --labels  ../sample_data/northwind_ground_truth.csv

Held-out 20% test split. Baselines scored on the same split:
  - majority class
  - the ticket's own category / subcategory field, as typed by the analyst
    (L1 maps the category field to its most common tower in training data)
  - legacy keyword rules (L1 only; their labels mapped onto the tower names)

Outputs: models/category_classifier.joblib, reports/category_model_report.json
"""

import argparse
import json
import os
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

from ml.category_model import LEVELS, CategoryClassifier, frame_for

SEED = 42
THRESHOLDS = [0.5, 0.7, 0.9]

# Legacy keyword-rule labels -> tower names used in the ground truth
LEGACY_TO_TOWER = {"Network": "Network", "Server": "Server", "Application": "Application",
                   "Database": "Database", "Security": "Security", "Hardware": "End User",
                   "Email": "Collaboration", "Cloud": "Server", "Other": "Application"}


def score(name, y_true, y_pred) -> dict:
    labels = sorted(set(y_true))
    return {"model": name,
            "accuracy": round(accuracy_score(y_true, y_pred), 4),
            "macro_f1": round(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0), 4)}


def legacy_rules_l1(raw: pd.DataFrame) -> np.ndarray:
    from services.ml_models import MultiTaskCategorizer
    rules = MultiTaskCategorizer()
    preds = [rules._predict_l1(str(d), None)[0] for d in raw["short_description"].fillna("")]
    return np.array([LEGACY_TO_TOWER.get(p, "Application") for p in preds])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickets", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--model-out", default="models/category_classifier.joblib")
    ap.add_argument("--report-dir", default="reports")
    args = ap.parse_args()

    raw = pd.read_csv(args.tickets).merge(pd.read_csv(args.labels), on="number")
    X = frame_for(raw)
    idx_train, idx_test = train_test_split(raw.index, test_size=0.2, stratify=raw["true_subcategory"],
                                           random_state=SEED)
    X_train, X_test = X.loc[idx_train], X.loc[idx_test]
    print(f"{len(raw)} tickets: train {len(idx_train)}, test {len(idx_test)}")

    clf = CategoryClassifier().fit(X_train, {lvl: raw.loc[idx_train, col].to_numpy() for lvl, col in LEVELS.items()})
    pred = clf.predict(X_test)

    report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "data": {"tickets": os.path.basename(args.tickets), "n": len(raw),
                       "split": {"train": len(idx_train), "test": len(idx_test)}},
              "levels": {}}
    for level, col in LEVELS.items():
        y_train, y_test = raw.loc[idx_train, col], raw.loc[idx_test, col]
        results = [score("Majority class", y_test, np.full(len(y_test), y_train.mode()[0]))]

        if level == "l2":
            field = raw.loc[idx_test, "subcategory"].fillna("").str.strip()
            results.append(score("Ticket's own subcategory field", y_test, field))
        else:
            field_map = raw.loc[idx_train].groupby(raw.loc[idx_train, "category"].fillna(""))[col].agg(
                lambda s: s.mode()[0])
            field_pred = raw.loc[idx_test, "category"].fillna("").map(field_map).fillna(y_train.mode()[0])
            results.append(score("Ticket's own category field", y_test, field_pred))
            results.append(score("Legacy keyword rules", y_test, legacy_rules_l1(raw.loc[idx_test])))

        results.append(score("Logistic regression (TF-IDF + fields)", y_test, pred[level]))

        conf = pred[f"{level}_confidence"].to_numpy()
        correct = (pred[level].to_numpy() == y_test.to_numpy())
        selective = [{"threshold": t, "coverage": round(float((conf >= t).mean()), 4),
                      "accuracy": round(float(correct[conf >= t].mean()), 4) if (conf >= t).any() else None}
                     for t in THRESHOLDS]

        errors = (pd.DataFrame({"true": y_test.to_numpy(), "pred": pred[level].to_numpy()})
                  .query("true != pred").value_counts().head(6))
        report["levels"][level] = {
            "target": col, "n_classes": int(y_train.nunique()), "test_results": results,
            "selective_accuracy": selective,
            "top_confusions": [{"true": t, "predicted": p, "count": int(c)} for (t, p), c in errors.items()],
        }
        print(f"\n{level} ({col}, {y_train.nunique()} classes)")
        for r in results:
            print(f"  {r['model']:40s} acc {r['accuracy']:.1%}  macro-F1 {r['macro_f1']:.3f}")
        print("  selective:", selective)

    os.makedirs(os.path.dirname(args.model_out) or ".", exist_ok=True)
    os.makedirs(args.report_dir, exist_ok=True)
    joblib.dump({"classifier": clf, "trained_at": report["generated_at"],
                 "training_data": os.path.basename(args.tickets), "n_train": len(idx_train)}, args.model_out)
    with open(os.path.join(args.report_dir, "category_model_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nModel -> {args.model_out}")


if __name__ == "__main__":
    main()
