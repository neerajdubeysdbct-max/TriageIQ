"""
Automation Status Classifier
Supervised model that predicts whether a ticket is Already Automated,
Can Be Automated or Manual Only, trained on labelled tickets.

Replaces the old rule-based "XGBoost" scorer (which had no trained model and
never scored a ticket below 50) with:
  - TF-IDF text features + structured ticket features
  - XGBoost multi-class model, early-stopped on a validation split
  - isotonic probability calibration
  - SHAP explanations (global and per ticket)
"""

import re
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.frozen import FrozenEstimator
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from utils import normalize_priority

CLASSES = ["Already Automated", "Can Be Automated", "Manual Only"]
AUTOMATABLE = ["Already Automated", "Can Be Automated"]

TEXT_COL = "text"
CATEGORICAL_COLS = ["priority_level", "contact_type", "assignment_group", "category"]
NUMERIC_COLS = ["log_mttr_hours", "reassignment_count", "reopen_count",
                "open_hour", "open_weekday", "resolver_is_bot", "closure_note_length"]

BOT_PATTERN = re.compile(r"bot|automation|auto[._-]|integration|monitor|ignio|system|sspr", re.I)

# first.last style user handles mentioned in free text (not file names like services.msc)
USER_HANDLE = re.compile(r"\b[a-z]{2,}\.[a-z]{2,}\b(?<!\.msc)(?<!\.exe)(?<!\.com)(?<!\.log)(?<!\.txt)")

# Score tiers on calibrated P(automatable) * 100
TIERS = [(75, "High"), (50, "Medium"), (25, "Low"), (0, "Not feasible")]


# ============================================================
# FEATURE PREPARATION
# ============================================================

def _first_present(df: pd.DataFrame, names: List[str]) -> pd.Series:
    """
    Coalesce candidate columns: per row, the first non-empty value. CSV exports
    and `tickets` rows name things differently (close_notes vs resolution_notes,
    contact_type vs channel), and DB rows often leave one of the pair empty.
    """
    result = pd.Series([None] * len(df), index=df.index, dtype=object)
    for name in names:
        if name in df.columns:
            col = df[name].where(df[name].astype(str).str.strip().ne("") & df[name].notna())
            result = result.where(result.notna(), col)
    return result


def _mask_names(text: str, names) -> str:
    for name in names:
        if isinstance(name, str) and len(name) > 2:
            text = text.replace(name.lower(), " person ")
            # also catch "aarav.das" / "das, aarav" style handles
            for part in re.split(r"[\s.,_]+", name.lower()):
                if len(part) > 2:
                    text = re.sub(rf"\b{re.escape(part)}\b", " ", text)
    return text


def prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map raw tickets (ServiceNow CSV columns or `tickets` table columns)
    onto the canonical model inputs.
    """
    out = pd.DataFrame(index=df.index)

    short = _first_present(df, ["short_description"]).fillna("").astype(str)
    desc = _first_present(df, ["description"]).fillna("").astype(str)
    notes = _first_present(df, ["close_notes", "resolution_notes"]).fillna("").astype(str)
    text = (short + " . " + desc + " . " + notes).str.lower()

    # Mask people's names (caller, assignee) so the model can't learn "who reported
    # it" as a shortcut, and no personal data ends up as a feature. resolved_by is
    # either the assignee or a bot, and bot names ("ignio.automation") are signal.
    people = pd.concat([_first_present(df, [c]) for c in
                        ("caller_id", "assigned_to", "requested_for")], axis=1)
    text = [_mask_names(t, names) for t, names in zip(text, people.itertuples(index=False))]
    text = [USER_HANDLE.sub(" person ", t) for t in text]

    # Site names should not decide the outcome either: mask every known location
    sites = {s.lower() for s in _first_present(df, ["location"]).dropna().astype(str) if len(s) > 2}
    if sites:
        site_re = re.compile(r"\b(" + "|".join(re.escape(s) for s in sorted(sites, key=len, reverse=True)) + r")\b")
        text = [site_re.sub(" site ", t) for t in text]
    out[TEXT_COL] = text

    out["priority_level"] = _first_present(df, ["priority"]).map(normalize_priority)
    out["contact_type"] = _first_present(df, ["contact_type", "channel"]).fillna("Unknown").astype(str)
    out["assignment_group"] = _first_present(df, ["assignment_group"]).fillna("Unknown").astype(str)
    out["category"] = _first_present(df, ["category"]).fillna("Unknown").astype(str)

    opened = pd.to_datetime(_first_present(df, ["opened_at", "opened"]), errors="coerce")
    resolved = pd.to_datetime(_first_present(df, ["resolved_at", "resolved"]), errors="coerce")
    mttr = pd.to_numeric(_first_present(df, ["mttr_hours"]), errors="coerce")
    mttr = mttr.fillna((resolved - opened).dt.total_seconds() / 3600)
    out["log_mttr_hours"] = np.log1p(mttr.clip(lower=0).fillna(mttr.median() if mttr.notna().any() else 0))

    out["reassignment_count"] = pd.to_numeric(_first_present(df, ["reassignment_count"]), errors="coerce").fillna(0)
    out["reopen_count"] = pd.to_numeric(_first_present(df, ["reopen_count"]), errors="coerce").fillna(0)
    out["open_hour"] = opened.dt.hour.fillna(12)
    out["open_weekday"] = opened.dt.dayofweek.fillna(3)

    resolver = _first_present(df, ["resolved_by", "sys_updated_by"]).fillna("").astype(str)
    out["resolver_is_bot"] = resolver.str.contains(BOT_PATTERN).astype(int)
    out["closure_note_length"] = notes.str.len()
    return out


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("text", TfidfVectorizer(ngram_range=(1, 2), min_df=5, max_df=0.5, max_features=2000,
                                 sublinear_tf=True, stop_words="english", token_pattern=r"(?u)\b[a-z][a-z]+\b"), TEXT_COL),
        ("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=10), CATEGORICAL_COLS),
        ("num", StandardScaler(), NUMERIC_COLS),
    ])


def readable_feature_name(raw: str) -> str:
    """'text__password reset' -> 'text: "password reset"', 'cat__contact_type_Phone' -> 'contact_type = Phone'."""
    block, _, name = raw.partition("__")
    if block == "text":
        return f'text: "{name}"'
    if block == "cat":
        for col in CATEGORICAL_COLS:
            if name.startswith(col + "_"):
                return f"{col} = {name[len(col) + 1:]}"
    return name


# ============================================================
# MODEL
# ============================================================

class AutomationClassifier:
    """Preprocessor + XGBoost + isotonic calibration, with SHAP explanations."""

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.preprocessor = build_preprocessor()
        self.encoder = LabelEncoder().fit(CLASSES)
        self.model: Optional[XGBClassifier] = None
        self.calibrated: Optional[CalibratedClassifierCV] = None
        self.feature_names: List[str] = []
        self._explainer = None

    # ---------- training ----------

    def fit(self, X_train: pd.DataFrame, y_train, X_val: pd.DataFrame, y_val) -> "AutomationClassifier":
        Xt = self.preprocessor.fit_transform(X_train)
        Xv = self.preprocessor.transform(X_val)
        self.feature_names = [readable_feature_name(n) for n in self.preprocessor.get_feature_names_out()]
        yt, yv = self.encoder.transform(y_train), self.encoder.transform(y_val)

        self.model = XGBClassifier(
            objective="multi:softprob", n_estimators=600, learning_rate=0.05, max_depth=4,
            subsample=0.8, colsample_bytree=0.5, min_child_weight=5, reg_lambda=5.0,
            eval_metric="mlogloss", early_stopping_rounds=40, tree_method="hist",
            random_state=self.random_state, n_jobs=-1,
        )
        self.model.fit(Xt, yt, sample_weight=compute_sample_weight("balanced", yt),
                       eval_set=[(Xv, yv)], verbose=False)

        # Calibrate on the validation split (the model never trained on it)
        self.calibrated = CalibratedClassifierCV(FrozenEstimator(self.model), method="isotonic")
        self.calibrated.fit(Xv, yv)
        self._explainer = None

        # What the training data looked like, for drift monitoring (services/drift.py)
        self.reference = build_reference(X_train, self.calibrated.predict_proba(Xv).max(axis=1),
                                         self.preprocessor.named_transformers_["text"].vocabulary_)
        return self

    # ---------- inference ----------

    def transform(self, X: pd.DataFrame):
        return self.preprocessor.transform(X)

    def predict_proba(self, X: pd.DataFrame, calibrated: bool = True) -> np.ndarray:
        Xm = self.transform(X)
        return (self.calibrated if calibrated else self.model).predict_proba(Xm)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.encoder.inverse_transform(self.predict_proba(X).argmax(axis=1))

    def score(self, X: pd.DataFrame) -> pd.DataFrame:
        """Per-ticket output used by the app: status, confidence, automation score and tier."""
        proba = self.predict_proba(X)
        idx = {c: i for i, c in enumerate(self.encoder.classes_)}
        automatable = proba[:, idx["Already Automated"]] + proba[:, idx["Can Be Automated"]]
        score = np.round(automatable * 100, 1)
        return pd.DataFrame({
            "predicted_status": self.encoder.inverse_transform(proba.argmax(axis=1)),
            "confidence": proba.max(axis=1).round(4),
            "automation_score": score,
            "feasibility_tier": [score_to_tier(s) for s in score],
            **{f"p_{c}": proba[:, i].round(4) for c, i in idx.items()},
        }, index=X.index)

    # ---------- explanations ----------

    @property
    def explainer(self):
        if self._explainer is None:
            import shap
            self._explainer = shap.TreeExplainer(self.model)
        return self._explainer

    def shap_values(self, X: pd.DataFrame) -> np.ndarray:
        """SHAP values in log-odds space, shape (n_tickets, n_features, n_classes)."""
        Xm = self.transform(X)
        Xm = Xm.toarray() if sp.issparse(Xm) else Xm
        values = np.asarray(self.explainer.shap_values(Xm))
        if values.ndim == 3 and values.shape[0] == len(CLASSES) and values.shape[0] != Xm.shape[0]:
            values = np.transpose(values, (1, 2, 0))  # older shap: list per class
        return values

    def global_importance(self, X: pd.DataFrame, top_n: int = 20) -> Dict:
        """Mean |SHAP| per feature, overall and per class."""
        values = self.shap_values(X)
        names = np.array(self.feature_names)
        overall = np.abs(values).mean(axis=(0, 2))
        order = np.argsort(overall)[::-1][:top_n]
        result = {"overall": [{"feature": names[i], "importance": round(float(overall[i]), 4)} for i in order]}
        for ci, cls in enumerate(self.encoder.classes_):
            per = np.abs(values[:, :, ci]).mean(axis=0)
            top = np.argsort(per)[::-1][:top_n]
            result[cls] = [{"feature": names[i], "importance": round(float(per[i]), 4)} for i in top]
        return result

    def explain_ticket(self, X_row: pd.DataFrame, top_n: int = 10) -> Dict:
        """Top features pushing one ticket towards its predicted class."""
        values = self.shap_values(X_row)[0]
        pred = int(self.predict_proba(X_row, calibrated=False).argmax(axis=1)[0])
        contrib = values[:, pred]
        order = np.argsort(np.abs(contrib))[::-1][:top_n]
        base = np.atleast_1d(self.explainer.expected_value)[pred]
        return {
            "predicted_status": self.encoder.classes_[pred],
            "base_value": round(float(base), 4),
            "contributions": [{"feature": self.feature_names[i], "shap": round(float(contrib[i]), 4)}
                              for i in order if contrib[i] != 0],
        }


DRIFT_NUMERIC = ["log_mttr_hours", "reassignment_count", "open_hour"]
DRIFT_CATEGORICAL = ["assignment_group", "category", "contact_type"]
LOW_CONFIDENCE = 0.6


def vocabulary_coverage(texts, vocabulary) -> float:
    """Share of words in the texts that the TF-IDF vocabulary knows (unigrams only)."""
    known = {k for k in vocabulary if " " not in k}
    words = [w for t in texts for w in re.findall(r"\b[a-z][a-z]+\b", t)]
    return sum(w in known for w in words) / max(len(words), 1)


def build_reference(X_train: pd.DataFrame, val_confidence: np.ndarray, vocabulary=None) -> Dict:
    """Snapshot of the training distribution: decile bins per numeric feature, seen categories, confidence."""
    numeric = {}
    for col in DRIFT_NUMERIC:
        edges = np.unique(np.quantile(X_train[col], np.linspace(0, 1, 11)))
        counts = np.histogram(np.clip(X_train[col], edges[0], edges[-1]), bins=edges)[0] if len(edges) > 1 else np.array([len(X_train)])
        numeric[col] = {"edges": edges.tolist(), "share": (counts / counts.sum()).tolist()}
    return {
        "numeric": numeric,
        "categorical": {col: sorted(X_train[col].astype(str).unique().tolist()) for col in DRIFT_CATEGORICAL},
        "low_confidence_share": float((val_confidence < LOW_CONFIDENCE).mean()),
        # what "normal" vocabulary coverage looks like on the training text itself
        "vocabulary_coverage": vocabulary_coverage(X_train[TEXT_COL], vocabulary) if vocabulary else None,
        "n_train": int(len(X_train)),
    }


def score_to_tier(score: float) -> str:
    for threshold, tier in TIERS:
        if score >= threshold:
            return tier
    return "Not feasible"
