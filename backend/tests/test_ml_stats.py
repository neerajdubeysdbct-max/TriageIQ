"""Statistics used for monitoring and evaluation: PSI, vocabulary coverage, Wilson interval."""

import numpy as np
import pytest

from ml.automation_model import vocabulary_coverage
from routers.review import wilson_interval
from services.drift import psi


def test_psi_teaching_example():
    # training shares [0.5, 0.3, 0.2]; new data [0.2, 0.3, 0.5] -> 0.55 (docs/teaching/04)
    edges = np.array([0, 1, 2, 3])
    values = np.array([0.5] * 20 + [1.5] * 30 + [2.5] * 50)
    assert psi([0.5, 0.3, 0.2], edges, values) == pytest.approx(0.5498, abs=1e-3)


def test_psi_zero_for_identical_distribution():
    edges = np.array([0, 1, 2])
    assert psi([0.5, 0.5], edges, np.array([0.5, 1.5] * 50)) == pytest.approx(0.0, abs=1e-9)


def test_psi_clips_out_of_range_values_into_edge_bins():
    edges = np.array([0, 1, 2])
    assert psi([0.5, 0.5], edges, np.array([-5.0, 9.0])) == pytest.approx(0.0, abs=1e-9)


def test_vocabulary_coverage():
    # input text is lowercased by prepare_frame before it gets here
    vocab = {"disk", "space", "alert", "low disk"}          # bigrams are ignored
    assert vocabulary_coverage(["disk space alert", "disk full"], vocab) == pytest.approx(4 / 5)
    assert vocabulary_coverage(["srv01 a"], vocab) == 0.0    # host names and 1-letter tokens are not words
    assert vocabulary_coverage([], vocab) == 0.0


def test_wilson_interval_matches_review_queue_result():
    # 55 of 60 labelled tickets correct -> 91.7%, 95% CI 81.9% to 96.4%
    lo, hi = wilson_interval(55, 60)
    assert (lo, hi) == pytest.approx((0.8194, 0.9640), abs=5e-4)


def test_wilson_interval_edge_cases():
    assert wilson_interval(0, 0) == (None, None)
    lo, hi = wilson_interval(10, 10)
    assert hi == pytest.approx(1.0) and 0.65 < lo < 0.75     # never claims certainty from 10 labels


def test_forecast_works_at_minimum_history():
    # the endpoint accepts 70 days; the first backtest origin then leaves ridge_lags only 14 days
    import pandas as pd
    from ml.forecast_model import forecast
    days = pd.date_range("2025-01-01", periods=70, freq="D")
    series = pd.Series([10.0 + (d.dayofweek == 0) * 5 for d in days], index=days)
    result = forecast(series)
    assert len(result["forecast"]) == 7
    assert all(row["lower"] <= row["predicted"] <= row["upper"] for row in result["forecast"])


def test_review_accuracy_excludes_labels_the_model_trained_on():
    # after a retrain on analyst labels, only gold-bucket labels or labels made later measure the model
    from datetime import datetime
    from routers.review import measures_active_model
    from services.model_lifecycle import _gold_bucket
    cutoff = datetime(2026, 10, 19, 3, 38)
    gold_id = next(i for i in range(1, 100) if _gold_bucket(i))
    pool_id = next(i for i in range(1, 100) if not _gold_bucket(i))
    before, after = datetime(2026, 10, 19, 3, 0), datetime(2026, 10, 19, 4, 0)
    assert measures_active_model(pool_id, before, None)            # base model: every label counts
    assert not measures_active_model(pool_id, before, cutoff)      # was training data
    assert measures_active_model(pool_id, after, cutoff)           # labelled after training
    assert measures_active_model(gold_id, before, cutoff)          # frozen gold set, never trained on


def test_stale_retraining_status_does_not_block_forever():
    from datetime import datetime
    from services.model_lifecycle import is_running
    status = {"state": "running", "started_at": "2026-10-19T09:00:00"}
    assert is_running(status, now=datetime(2026, 10, 19, 9, 0, 30))
    assert not is_running(status, now=datetime(2026, 10, 19, 12, 0))
    assert not is_running({"state": "done", "started_at": "2026-10-19T09:00:00"})
    assert not is_running(None)
