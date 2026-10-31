"""
Drift monitoring: does a new upload look like the data the active model was
trained on? Run after the automation model scores an upload.

Signals
  feature drift   Population Stability Index (PSI) of resolution time,
                  reassignments and opening hour vs. the training deciles
                  (< 0.1 stable, 0.1-0.25 moderate, > 0.25 significant)
  vocabulary      share of the upload's words the text model has seen
  categories      share of tickets whose team / category / channel value was
                  never seen in training
  confidence      share of tickets the model is unsure about (< 0.6) vs. the
                  same share on its validation data
"""

import json
import os
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ml.automation_model import DRIFT_CATEGORICAL, DRIFT_NUMERIC, LOW_CONFIDENCE

PSI_MODERATE, PSI_SIGNIFICANT = 0.1, 0.25
VOCAB_DROP_MODERATE = 0.08    # known-word share this far below the training text's own share
VOCAB_DROP_SIGNIFICANT = 0.15
UNSEEN_WARN = 0.3         # above this share of tickets with unseen team/category values
CONFIDENCE_WARN = 2.0     # unsure tickets at more than 2x the validation rate
COLUMN_NAMES = {"assignment_group": "team", "category": "category", "contact_type": "channel"}


def psi(reference_share, edges, values) -> float:
    actual = np.histogram(np.clip(values, edges[0], edges[-1]), bins=edges)[0].astype(float)
    actual = actual / max(actual.sum(), 1)
    expected = np.asarray(reference_share, dtype=float)
    a, e = np.clip(actual, 1e-4, None), np.clip(expected, 1e-4, None)
    return float(np.sum((a - e) * np.log(a / e)))


def assess(clf, X: pd.DataFrame, confidence: np.ndarray) -> Optional[Dict]:
    ref = getattr(clf, "reference", None)
    if not ref:
        return None
    findings, worst = [], "stable"

    def flag(level, message):
        nonlocal worst
        findings.append({"level": level, "message": message})
        order = ["stable", "moderate", "significant"]
        worst = max(worst, level, key=order.index)

    features = {}
    for col in DRIFT_NUMERIC:
        r = ref["numeric"][col]
        if len(r["edges"]) < 2:
            continue
        value = round(psi(r["share"], r["edges"], X[col].to_numpy()), 3)
        features[col] = value
        if value > PSI_SIGNIFICANT:
            flag("significant", f"{col.replace('_', ' ')} distribution has shifted (PSI {value})")
        elif value > PSI_MODERATE:
            flag("moderate", f"{col.replace('_', ' ')} distribution has shifted somewhat (PSI {value})")

    from ml.automation_model import vocabulary_coverage
    known = vocabulary_coverage(X["text"], clf.preprocessor.named_transformers_["text"].vocabulary_)
    baseline_vocab = ref.get("vocabulary_coverage")
    if baseline_vocab is None:
        baseline_vocab = _base_vocabulary_coverage(clf)
    if baseline_vocab is not None:
        drop = baseline_vocab - known
        if drop > VOCAB_DROP_SIGNIFICANT:
            flag("significant", f"text model knows {known:.0%} of the words here vs {baseline_vocab:.0%} on its training text")
        elif drop > VOCAB_DROP_MODERATE:
            flag("moderate", f"text model knows {known:.0%} of the words here vs {baseline_vocab:.0%} on its training text")

    unseen = {}
    for col in DRIFT_CATEGORICAL:
        seen = set(ref["categorical"][col])
        unseen[col] = round(float((~X[col].astype(str).isin(seen)).mean()), 4)
    worst_col = max(unseen, key=unseen.get)
    if unseen[worst_col] > UNSEEN_WARN:
        flag("significant" if unseen[worst_col] > 0.6 else "moderate",
             f"{unseen[worst_col]:.0%} of tickets have a {COLUMN_NAMES[worst_col]} never seen in training")

    low_conf = float((confidence < LOW_CONFIDENCE).mean())
    baseline = ref["low_confidence_share"]
    if low_conf > max(baseline * CONFIDENCE_WARN, 0.05):
        flag("moderate", f"model is unsure on {low_conf:.0%} of tickets vs {baseline:.0%} on validation data")

    return {
        "status": worst,
        "findings": findings,
        "psi": features,
        "known_vocabulary_share": round(known, 4),
        "training_vocabulary_share": round(baseline_vocab, 4) if baseline_vocab is not None else None,
        "unseen_category_share": unseen,
        "low_confidence_share": round(low_conf, 4),
        "validation_low_confidence_share": round(baseline, 4),
        "recommendation": {
            "stable": "Data resembles the training data.",
            "moderate": "Some differences from training data; review a sample of tickets.",
            "significant": "This data differs from what the model was trained on. Label a random sample in the "
                           "Review Queue to measure accuracy before relying on predictions.",
        }[worst],
    }


_BASE_COVERAGE: Dict[int, float] = {}


def _base_vocabulary_coverage(clf) -> Optional[float]:
    """For models saved before the reference stored it: coverage on the base training text."""
    key = id(clf)
    if key not in _BASE_COVERAGE:
        try:
            from config import BASE_TRAINING_TICKETS
            from ml.automation_model import prepare_frame, vocabulary_coverage
            X = prepare_frame(pd.read_csv(BASE_TRAINING_TICKETS))
            _BASE_COVERAGE[key] = vocabulary_coverage(X["text"], clf.preprocessor.named_transformers_["text"].vocabulary_)
        except Exception:
            return None
    return _BASE_COVERAGE[key]


def save(upload_id: int, report: Dict):
    os.makedirs(f"outputs/upload_{upload_id}", exist_ok=True)
    with open(f"outputs/upload_{upload_id}/drift.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


def load(upload_id: int) -> Optional[Dict]:
    path = f"outputs/upload_{upload_id}/drift.json"
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
