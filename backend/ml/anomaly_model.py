"""
Operational anomaly detection (unsupervised).

IsolationForest over context-aware features: what is unusual depends on the
ticket type. A 20-hour fix is normal for an application defect and extreme for
a password reset, and a 3 a.m. ticket is normal for a monitoring alert but odd
for a service-desk request. So features are measured against the ticket's own
group (its L2 subcategory), using robust statistics (median / MAD) that the
anomalies themselves can't drag around.
"""

from typing import List

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURES = ["mttr_dev", "reassignment_count", "reopen_count", "offhours_unusual", "p1_offhours_unusual"]
CONTAMINATION = 0.03   # share of tickets flagged; the operating point reported in evaluation
MIN_GROUP = 15         # smaller groups fall back to global statistics


def _robust_z(values: pd.Series, groups: pd.Series) -> pd.Series:
    glob_med = values.median()
    glob_mad = (values - glob_med).abs().median() or 1.0
    med = values.groupby(groups).transform("median")
    mad = values.groupby(groups).transform(lambda v: (v - v.median()).abs().median())
    size = values.groupby(groups).transform("size")
    med = med.where(size >= MIN_GROUP, glob_med)
    mad = mad.where((size >= MIN_GROUP) & (mad > 0), glob_mad)
    return (values - med) / (1.4826 * mad)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    df needs: mttr_hours, reassignment_count, reopen_count, opened (datetime),
    priority_level (P1..P4) and group (the ticket type, e.g. L2 subcategory).
    """
    group = df["group"].fillna("Unknown").astype(str)
    log_mttr = np.log1p(pd.to_numeric(df["mttr_hours"], errors="coerce").clip(lower=0))
    log_mttr = log_mttr.fillna(log_mttr.median())
    hour = pd.to_datetime(df["opened"], errors="coerce").dt.hour
    offhours = ((hour < 6) | (hour >= 22)).astype(float).fillna(0)
    group_offhours_share = offhours.groupby(group).transform("mean")
    p1 = (df["priority_level"] == "P1").astype(float)
    return pd.DataFrame({
        "mttr_dev": _robust_z(log_mttr, group).clip(-10, 10),
        "reassignment_count": pd.to_numeric(df["reassignment_count"], errors="coerce").fillna(0),
        "reopen_count": pd.to_numeric(df["reopen_count"], errors="coerce").fillna(0),
        # off-hours only counts as unusual where that group rarely works off-hours
        "offhours_unusual": offhours * (1 - group_offhours_share),
        "p1_offhours_unusual": p1 * offhours * (1 - group_offhours_share),
    }, index=df.index)


def score(features: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """Anomaly score in [0, 1] (higher = more unusual), the flag at CONTAMINATION, and reasons."""
    model = IsolationForest(n_estimators=300, contamination=CONTAMINATION, random_state=seed)
    model.fit(features[FEATURES])
    raw = -model.score_samples(features[FEATURES])
    norm = (raw - raw.min()) / ((raw.max() - raw.min()) or 1.0)
    return pd.DataFrame({
        "anomaly_score": norm.round(4),
        "is_anomaly": model.predict(features[FEATURES]) == -1,
        "reasons": [explain(row) for row in features.itertuples(index=False)],
    }, index=features.index)


def explain(row) -> List[str]:
    reasons = []
    if row.mttr_dev >= 3:
        reasons.append(f"Resolution time {row.mttr_dev:.1f} robust SDs above its ticket type")
    if row.reassignment_count >= 4:
        reasons.append(f"Reassigned {int(row.reassignment_count)} times")
    if row.reopen_count >= 1:
        reasons.append("Reopened after resolution")
    if row.p1_offhours_unusual > 0.5:
        reasons.append("P1 raised off-hours on a ticket type that rarely occurs then")
    elif row.offhours_unusual > 0.5:
        reasons.append("Raised off-hours, unusual for this ticket type")
    return reasons or ["Unusual combination of features"]


def global_mttr_z(df: pd.DataFrame) -> np.ndarray:
    """Baseline: plain z-score of MTTR against the whole dataset."""
    m = pd.to_numeric(df["mttr_hours"], errors="coerce").fillna(0)
    return ((m - m.mean()) / (m.std() or 1)).to_numpy()


def legacy_rule_score(df: pd.DataFrame) -> np.ndarray:
    """Baseline: the previous hand-weighted score (MTTR z, reassignments, reopens, SLA)."""
    from utils import SLA_HOURS
    m = pd.to_numeric(df["mttr_hours"], errors="coerce").fillna(0)
    z = (m - m.mean()) / (m.std() or 1)
    r = pd.to_numeric(df["reassignment_count"], errors="coerce").fillna(0)
    o = pd.to_numeric(df["reopen_count"], errors="coerce").fillna(0)
    sla = df["priority_level"].map(SLA_HOURS).fillna(24.0)
    s = (np.where(z.abs() > 2, np.minimum(z.abs() / 5, 0.4), 0)
         + np.where(r >= 3, np.minimum(r / 10, 0.25), 0)
         + np.where(o >= 1, np.minimum(o / 5, 0.2), 0)
         + np.where(df["priority_level"].isin(["P1", "P2"]) & (m > sla * 1.5), 0.2, 0))
    return np.asarray(s, dtype=float)
