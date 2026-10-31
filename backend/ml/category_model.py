"""
Ticket Category Classifier
Supervised L1 (tower) and L2 (subcategory) classification, replacing the
keyword rules whose "confidences" were constants.

Creation-time features only: what is known when a ticket is opened (short
description, description, channel, category field, priority). Closure notes,
the resolver and the assigned team are excluded: they don't exist yet when a
ticket needs routing, and the team *is* the routing decision (target leakage).

TF-IDF word + character n-grams (robust to typos and casing) plus the
ticket's own category / channel / priority fields, into a multinomial logistic
regression. Probabilities give a real confidence per ticket.
"""

from typing import Dict

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder

from ml.automation_model import TEXT_COL, prepare_frame

LEVELS = {"l1": "true_tower", "l2": "true_subcategory"}
FIELD_COLS = ["category", "contact_type", "priority_level"]


def build_pipeline(C: float = 4.0) -> Pipeline:
    features = ColumnTransformer([
        ("words", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True,
                                  stop_words="english"), TEXT_COL),
        ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3,
                                  sublinear_tf=True, max_features=20000), TEXT_COL),
        ("fields", OneHotEncoder(handle_unknown="ignore", min_frequency=5), FIELD_COLS),
    ])
    return make_pipeline(features, LogisticRegression(C=C, max_iter=3000, class_weight="balanced"))


class CategoryClassifier:
    """One pipeline per level (l1 tower, l2 subcategory)."""

    def __init__(self):
        self.models: Dict[str, Pipeline] = {}

    def fit(self, X: pd.DataFrame, labels: Dict[str, np.ndarray]) -> "CategoryClassifier":
        for level, y in labels.items():
            self.models[level] = build_pipeline().fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=X.index)
        for level, model in self.models.items():
            proba = model.predict_proba(X)
            out[level] = model.classes_[proba.argmax(axis=1)]
            out[f"{level}_confidence"] = proba.max(axis=1).round(4)
        return out


RESOLUTION_COLS = ["close_notes", "resolution_notes", "work_notes"]


def frame_for(df: pd.DataFrame) -> pd.DataFrame:
    """Creation-time model inputs from raw tickets (CSV export or tickets table rows)."""
    opened_view = df.drop(columns=[c for c in RESOLUTION_COLS if c in df.columns])
    return prepare_frame(opened_view)
