"""Stage 3 — exploratory data analysis: per-column profiles and the time axis."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as st

from .ingest import ColumnSchema


def _f(x) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(x) or np.isinf(x) else x


def profile(df: pd.DataFrame, schema: list[ColumnSchema]) -> dict:
    cols: dict[str, dict] = {}
    for c in schema:
        s = df[c.name]
        p: dict = {"semantic": c.semantic, "missing": int(s.isna().sum()),
                   "unique": int(s.astype(str).nunique())}
        if c.semantic == "numeric":
            v = s.dropna().astype(float)
            if len(v):
                p.update({
                    "count": int(len(v)), "mean": _f(v.mean()), "median": _f(v.median()),
                    "std": _f(v.std()), "min": _f(v.min()), "max": _f(v.max()),
                    "q1": _f(v.quantile(.25)), "q3": _f(v.quantile(.75)),
                    "skew": _f(st.skew(v)) if len(v) > 2 else None,
                    "kurtosis": _f(st.kurtosis(v)) if len(v) > 3 else None,
                    "sum": _f(v.sum()),
                    "histogram": _histogram(v),
                })
        elif c.semantic in ("categorical", "boolean"):
            vc = s.astype(str).value_counts()
            probs = vc / vc.sum()
            p.update({
                "levels": int(len(vc)),
                "top": [{"value": k, "count": int(v), "share": _f(v / vc.sum())} for k, v in vc.head(12).items()],
                "entropy": _f(-(probs * np.log2(probs)).sum()),
            })
        elif c.semantic == "datetime":
            v = s.dropna()
            if len(v):
                p.update({"min": v.min().isoformat(), "max": v.max().isoformat(),
                          "span_days": _f((v.max() - v.min()).total_seconds() / 86400)})
        cols[c.name] = p
    return {"columns": cols, "time_axis": pick_time_axis(df, schema)}


def _histogram(v: pd.Series, bins: int = 24) -> dict:
    counts, edges = np.histogram(v, bins=min(bins, max(5, int(np.sqrt(len(v))))))
    return {"counts": counts.tolist(), "edges": [float(e) for e in edges]}


def pick_time_axis(df: pd.DataFrame, schema: list[ColumnSchema]) -> dict | None:
    """Choose the datetime column (if any) to use for trend analysis and its resample frequency."""
    best = None
    for c in schema:
        if c.semantic != "datetime":
            continue
        s = df[c.name].dropna()
        if s.nunique() < 4:
            continue
        if best is None or s.nunique() > best[1]:
            best = (c.name, s.nunique())
    if not best:
        return None
    name = best[0]
    s = df[name].dropna()
    span_days = (s.max() - s.min()).total_seconds() / 86400
    is_year = next((c.note == "year" for c in schema if c.name == name), False)
    uniq = np.sort(s.unique())
    native = float(np.median(np.diff(uniq)) / np.timedelta64(1, "D")) if len(uniq) > 1 else 1.0
    # Finest period at or above the data's own resolution that yields a readable number of bins.
    candidates = [("h", "hour", 1 / 24), ("D", "day", 1), ("W", "week", 7), ("MS", "month", 30.44),
                  ("QS", "quarter", 91.3), ("YS", "year", 365.25)]
    freq, label = "YS", "year"
    if not is_year:
        for f, lab, days in candidates:
            if days >= native * 0.9 and span_days / days <= MAX_TIME_BINS:
                freq, label = f, lab
                break
    return {"column": name, "freq": freq, "unit": label, "span_days": float(span_days),
            "native_days": native, "start": s.min().isoformat(), "end": s.max().isoformat()}


MAX_TIME_BINS = 400
