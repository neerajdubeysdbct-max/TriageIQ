"""
Daily ticket-volume forecasting with backtest-based model selection.

Candidates (all forecast `horizon` days ahead from a history of daily counts):
  - seasonal_naive : repeat the last observed week
  - dow_mean       : per-weekday mean of the last 8 weeks (the previous approach, minus its trend term)
  - ridge_lags     : ridge regression on lags 1-14 + weekday, applied recursively
  - lstm           : small LSTM over a 28-day window (+ weekday encoding) predicting the next 7 days

Rolling-origin backtest picks the model, preferring the simplest candidate
whose MAE is within PARSIMONY_TOLERANCE of the best (a complex model has to win
clearly, not by noise); prediction intervals are the
empirical 10th-90th percentiles of that model's backtest errors per horizon
step, so they reflect how wrong the model actually was, not a formula.
"""

from typing import Callable, Dict

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

HORIZON = 7
PARSIMONY_TOLERANCE = 0.03   # simpler model kept unless beaten by more than 3% MAE
N_ORIGINS = 8
LAGS = 14
WINDOW = 28


def daily_series(timestamps) -> pd.Series:
    """Daily counts with explicit zeros for days without tickets."""
    ts = pd.to_datetime(pd.Series(timestamps), errors="coerce").dropna()
    counts = ts.dt.floor("D").value_counts().sort_index()
    full = pd.date_range(counts.index.min(), counts.index.max(), freq="D")
    return counts.reindex(full, fill_value=0).astype(float)


# ---------------- candidate models: history -> next `h` days ----------------

def seasonal_naive(hist: pd.Series, h: int) -> np.ndarray:
    last_week = hist.to_numpy()[-7:]
    return np.resize(last_week, h)


def dow_mean(hist: pd.Series, h: int) -> np.ndarray:
    recent = hist.iloc[-56:]
    means = recent.groupby(recent.index.dayofweek).mean()
    future = pd.date_range(hist.index[-1] + pd.Timedelta(days=1), periods=h, freq="D")
    return np.array([means.get(d.dayofweek, recent.mean()) for d in future])


def _lag_row(values: np.ndarray, day) -> np.ndarray:
    dow = np.zeros(7)
    dow[day.dayofweek] = 1
    return np.concatenate([values[-LAGS:][::-1], dow])


def ridge_lags(hist: pd.Series, h: int) -> np.ndarray:
    v, idx = hist.to_numpy(), hist.index
    if len(v) < LAGS + 10:   # too few rows to fit; the earliest backtest origin can hit this
        return dow_mean(hist, h)
    X = np.array([_lag_row(v[:i], idx[i]) for i in range(LAGS, len(v))])
    model = Ridge(alpha=1.0).fit(X, v[LAGS:])
    out, values = [], list(v)
    for step in range(h):
        day = idx[-1] + pd.Timedelta(days=step + 1)
        pred = max(float(model.predict(_lag_row(np.array(values), day)[None])[0]), 0.0)
        out.append(pred)
        values.append(pred)
    return np.array(out)


def lstm(hist: pd.Series, h: int, epochs: int = 150, seed: int = 0) -> np.ndarray:
    import torch
    from torch import nn

    torch.manual_seed(seed)
    v = hist.to_numpy(dtype=np.float32)
    scale = float(v.mean() or 1.0)
    dow = hist.index.dayofweek.to_numpy()
    feats = np.stack([v / scale, np.sin(2 * np.pi * dow / 7), np.cos(2 * np.pi * dow / 7)], axis=1).astype(np.float32)

    xs, ys = [], []
    for i in range(WINDOW, len(v) - h + 1):
        xs.append(feats[i - WINDOW:i])
        ys.append(v[i:i + h] / scale)
    if len(xs) < 10:
        return dow_mean(hist, h)
    X, Y = torch.tensor(np.array(xs)), torch.tensor(np.array(ys))

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.rnn = nn.LSTM(3, 32, batch_first=True)
            self.head = nn.Linear(32, h)

        def forward(self, x):
            _, (hidden, _) = self.rnn(x)
            return self.head(hidden[-1])

    net = Net()
    opt = torch.optim.Adam(net.parameters(), lr=0.01)
    for _ in range(epochs):
        opt.zero_grad()
        loss = nn.functional.mse_loss(net(X), Y)
        loss.backward()
        opt.step()
    with torch.no_grad():
        pred = net(torch.tensor(feats[-WINDOW:][None]))[0].numpy() * scale
    return np.clip(pred, 0, None)


CANDIDATES: Dict[str, Callable] = {
    "seasonal_naive": seasonal_naive, "dow_mean": dow_mean, "ridge_lags": ridge_lags, "lstm": lstm,
}


# ---------------- backtest and forecast ----------------

def backtest(series: pd.Series, horizon: int = HORIZON, n_origins: int = N_ORIGINS) -> Dict:
    """Rolling-origin backtest over the last n_origins * horizon days."""
    origins = [len(series) - horizon * k for k in range(n_origins, 0, -1)]
    errors = {name: [] for name in CANDIDATES}
    for origin in origins:
        hist, actual = series.iloc[:origin], series.iloc[origin:origin + horizon].to_numpy()
        for name, fn in CANDIDATES.items():
            errors[name].append(fn(hist, horizon) - actual)
    results = {}
    for name, errs in errors.items():
        e = np.array(errs)                       # (origins, horizon)
        results[name] = {"mae": round(float(np.abs(e).mean()), 3),
                         "rmse": round(float(np.sqrt((e ** 2).mean())), 3),
                         "errors": e}
    base = results["seasonal_naive"]["mae"] or 1.0
    for r in results.values():
        r["mae_vs_seasonal_naive"] = round(r["mae"] / base, 3)
    lowest = min(r["mae"] for r in results.values())
    # CANDIDATES is ordered simplest first
    best = next(name for name in CANDIDATES if results[name]["mae"] <= lowest * (1 + PARSIMONY_TOLERANCE))
    lowest_name = min(results, key=lambda k: results[k]["mae"])
    return {"results": results, "best": best, "lowest_mae_model": lowest_name,
            "origins": len(origins), "horizon": horizon}


def forecast(series: pd.Series, days: int = HORIZON) -> Dict:
    """Backtest, pick the best model, forecast with empirical 80% intervals."""
    bt = backtest(series)
    best = bt["best"]
    errs = bt["results"][best]["errors"]
    preds = CANDIDATES[best](series, days)
    lo_q = np.percentile(errs, 10, axis=0)
    hi_q = np.percentile(errs, 90, axis=0)
    rows = []
    for i, p in enumerate(preds):
        step = min(i, errs.shape[1] - 1)
        rows.append({"date": (series.index[-1] + pd.Timedelta(days=i + 1)).strftime("%Y-%m-%d"),
                     "predicted": round(float(p), 1),
                     # error = prediction - actual, so actual = prediction - error
                     "lower": round(max(float(p - hi_q[step]), 0.0), 1),
                     "upper": round(float(p - lo_q[step]), 1)})
    summary = {name: {k: v for k, v in r.items() if k != "errors"} for name, r in bt["results"].items()}
    return {"model": best, "lowest_mae_model": bt["lowest_mae_model"], "parsimony_tolerance": PARSIMONY_TOLERANCE,
            "backtest": summary, "origins": bt["origins"], "horizon": bt["horizon"], "forecast": rows}
