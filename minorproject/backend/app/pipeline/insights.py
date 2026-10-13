"""Stage 5 — insight extraction and anomaly detection.

Turns the significant statistical tests into ranked, de-duplicated *findings*
(each carrying the exact verified numbers a story may cite), and detects
anomalies three ways: robust z-scores per measure, an Isolation Forest across
all measures, and spikes in the time series.
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

from . import fmt
from .ingest import ColumnSchema
from .stats import resample_series

KIND_WEIGHT = {"trend": 1.0, "group_difference": 0.75, "correlation": 0.7, "association": 0.6,
               "anomaly": 0.7, "spike": 0.85, "concentration": 0.65}
MAX_FINDINGS = 8
ROBUST_Z = 3.5
MIN_SPIKE_REL = 0.15  # a spike must differ from its local baseline by at least 15%


def _effect_norm(t: dict) -> float:
    e = abs(t.get("effect") or 0)
    return {"d": min(e / 1.5, 1), "eta2": min(e / 0.3, 1)}.get(t["effect_name"], min(e, 1))


def _score(kind: str, q: float | None, effect: float) -> float:
    sig = min(-math.log10(max(1.0 if q is None else q, 1e-12)), 10) / 10
    return round(0.35 * sig + 0.35 * effect + 0.30 * KIND_WEIGHT.get(kind, 0.5), 4)


# ---------------------------------------------------------------------------- facts
def _fact(label: str, value, display: str | None = None) -> dict:
    return {"label": label, "value": value, "display": display or fmt.num(value)}


def _finding_from_test(t: dict) -> dict:
    d, cols, kind = t["details"], t["columns"], t["kind"]
    stat_block = {"test": t["test"], "statistic": t["statistic"], "p": t["p"], "q": t.get("q"),
                  "effect": t["effect"], "effect_name": t["effect_name"], "magnitude": t["magnitude"],
                  "n": t["n"]}
    facts: list[dict] = []
    if kind == "correlation":
        a, b = cols
        title = (f"{fmt.title(a)} and {fmt.humanize(b)} move "
                 f"{'together' if d['direction'] == 'positive' else 'in opposite directions'}")
        facts += [_fact("Pearson r", round(t["effect"], 2)),
                  _fact("Variance explained (R²)", round(d["r2"] * 100, 1), fmt.pct(d["r2"] * 100)),
                  _fact("Spearman ρ", round(d["spearman_rho"], 2)),
                  _fact(f"Change in {fmt.humanize(b)} per unit of {fmt.humanize(a)}", d["slope"]),
                  _fact("Observations", t["n"])]
    elif kind == "group_difference":
        cat, measure = cols
        g = d["groups"]
        hi, lo = d["highest"], d["lowest"]
        title = f"{fmt.title(measure)} varies sharply by {fmt.humanize(cat)} — {hi} leads"
        if len(g) == 2:
            if {hi, lo} <= {"Yes", "No", "True", "False"}:
                title = f"{fmt.title(measure)} is markedly higher where {fmt.humanize(cat)} is '{hi}'"
            else:
                title = f"{fmt.title(measure)} is markedly higher for {hi} than {lo}"
        facts += [_fact(f"Average {fmt.humanize(measure)} — {hi}", g[hi]["mean"]),
                  _fact(f"Average {fmt.humanize(measure)} — {lo}", g[lo]["mean"])]
        if d.get("ratio") and d["ratio"] > 0:
            facts.append(_fact(f"{hi} vs {lo} ratio", round(d["ratio"], 2), f"{d['ratio']:.2f}×"))
        facts += [_fact("Groups compared", len(g)), _fact("Observations", t["n"])]
    elif kind == "association":
        a, b = cols
        cell = d["strongest_cell"]
        title = f"{fmt.title(a)} and {fmt.humanize(b)} are linked"
        facts += [_fact("Cramér's V", round(t["effect"], 2)),
                  _fact(f"Observed '{cell['row']}' × '{cell['col']}'", cell["observed"]),
                  _fact(f"Expected if unrelated", round(cell["expected"], 1)),
                  _fact("Observations", t["n"])]
    elif kind == "trend":
        measure, unit = d["measure"], d["unit"]
        verb = "climbing" if d["direction"] == "rising" else "falling"
        title = f"{fmt.title(measure)} is {verb} {'' if unit == 'hour' else 'steadily '}over time".replace("  ", " ")
        series = d["series"]
        facts += [_fact(f"{fmt.title(measure)} — first {unit} ({fmt.date(series[0]['t'], unit)})", d["first"]),
                  _fact(f"{fmt.title(measure)} — latest {unit} ({fmt.date(series[-1]['t'], unit)})", d["last"])]
        if d.get("pct_change") is not None:
            facts.append(_fact("Change over the period", round(d["pct_change"], 1), fmt.pct(d["pct_change"], True)))
        facts += [_fact(f"Peak ({fmt.date(d['peak']['t'], unit)})", d["peak"]["v"]),
                  _fact(f"Trend per {unit} (OLS slope)", d["slope"]),
                  _fact("Kendall τ", round(t["effect"], 2)),
                  _fact(f"{unit.title()}s analysed", len(series))]
    return {
        "id": t["id"], "kind": kind, "title": title, "columns": cols, "stat": stat_block,
        "details": d, "facts": facts,
        "score": _score(kind, t.get("q"), _effect_norm(t)),
    }


# ---------------------------------------------------------------------------- anomalies
def _label_column(df: pd.DataFrame, schema: list[ColumnSchema]) -> str | None:
    best, best_u = None, 0
    for c in schema:
        if c.semantic in ("text", "id", "categorical") and c.name in df.columns:
            u = df[c.name].astype(str).nunique()
            if u > best_u:
                best, best_u = c.name, u
    return best


def _row_label(df: pd.DataFrame, i, label_col: str | None, time_col: str | None) -> str:
    parts = []
    if label_col:
        parts.append(str(df.at[i, label_col]))
    if time_col and pd.notna(df.at[i, time_col]):
        parts.append(pd.Timestamp(df.at[i, time_col]).strftime("%d %b %Y %H:%M").replace(" 00:00", ""))
    return " · ".join(parts) or f"Row {int(i) + 1}"


def detect_anomalies(df: pd.DataFrame, schema: list[ColumnSchema], time_axis: dict | None,
                     outlier_flags: dict) -> dict:
    numeric = [c.name for c in schema if c.semantic == "numeric" and df[c.name].nunique() > 5]
    label_col = _label_column(df, schema)
    time_col = time_axis["column"] if time_axis else None

    points: list[dict] = []
    for col in numeric:
        v = df[col].astype(float)
        med = v.median()
        mad = (v - med).abs().median()
        if not mad or np.isnan(mad):
            continue
        z = 0.6745 * (v - med) / mad
        for i in z[z.abs() > ROBUST_Z].abs().sort_values(ascending=False).head(5).index:
            points.append({"row": int(i), "label": _row_label(df, i, label_col, time_col), "column": col,
                           "value": float(v[i]), "median": float(med), "robust_z": round(float(z[i]), 2),
                           "direction": "above" if z[i] > 0 else "below"})
    points.sort(key=lambda p: -abs(p["robust_z"]))

    multivariate: list[dict] = []
    if len(numeric) >= 2 and len(df) >= 50:
        X = df[numeric].astype(float)
        X = X.fillna(X.median())
        Xs = RobustScaler().fit_transform(X)
        forest = IsolationForest(n_estimators=200, contamination="auto", random_state=42).fit(Xs)
        scores = -forest.score_samples(Xs)
        flagged = np.where(forest.predict(Xs) == -1)[0]
        for i in flagged[np.argsort(-scores[flagged])][:8]:
            drivers = sorted(zip(numeric, Xs[i]), key=lambda kv: -abs(kv[1]))[:2]
            multivariate.append({
                "row": int(i), "label": _row_label(df, df.index[i], label_col, time_col),
                "score": round(float(scores[i]), 3),
                "drivers": [{"column": c, "value": float(X.iloc[i][c]), "scaled": round(float(s), 2)}
                            for c, s in drivers]})
        multivariate_share = float(len(flagged) / len(df))
    else:
        multivariate_share = 0.0

    spikes: list[dict] = []
    if time_axis:
        for value in [None] + numeric[:6]:
            try:
                cols = [time_col] + ([value] if value else [])
                series = resample_series(df[cols], time_col, time_axis["freq"], value)
            except Exception:
                continue
            if len(series) < 8:
                continue
            base = series.rolling(5, center=True, min_periods=3).median()
            resid = series - base
            mad = (resid - resid.median()).abs().median()
            if not mad or np.isnan(mad):
                continue
            z = 0.6745 * (resid - resid.median()) / mad
            for t in z[z.abs() > ROBUST_Z].abs().sort_values(ascending=False).head(3).index:
                rel = abs(resid[t]) / abs(base[t]) if base[t] else float("inf")
                if rel < MIN_SPIKE_REL:
                    continue  # statistically odd but too small to matter to a reader
                spikes.append({"measure": value or "record count", "t": t.isoformat(), "unit": time_axis["unit"],
                               "value": float(series[t]), "expected": float(base[t]),
                               "robust_z": round(float(z[t]), 2), "rel_dev": round(float(min(rel, 99)), 3),
                               "direction": "spike" if z[t] > 0 else "dip"})
        spikes.sort(key=lambda s: -abs(s["robust_z"]))

    return {"points": points[:20], "multivariate": multivariate,
            "multivariate_share": multivariate_share, "spikes": spikes[:10],
            "label_column": label_col, "iqr_flags": {k: v["count"] for k, v in outlier_flags.items()}}


def _concentration(df: pd.DataFrame, schema: list[ColumnSchema]) -> list[dict]:
    out = []
    for c in schema:
        if c.semantic != "numeric":
            continue
        v = df[c.name].dropna().astype(float)
        if len(v) < 30 or (v < 0).any() or v.sum() <= 0:
            continue
        top = v.sort_values(ascending=False)
        k = max(1, int(round(len(v) * 0.1)))
        share = float(top.head(k).sum() / v.sum() * 100)
        if share >= 50:
            out.append({
                "id": f"conc:{c.name}", "kind": "concentration",
                "title": f"A small minority accounts for most of the {fmt.humanize(c.name)}",
                "columns": [c.name], "stat": {"test": "Top-decile share", "n": int(len(v))},
                "details": {"share_top10": share, "k": k, "n": int(len(v)), "total": float(v.sum())},
                "facts": [_fact("Share held by the top 10% of records", round(share, 1), fmt.pct(share)),
                          _fact("Records in the top 10%", k), _fact("Total", float(v.sum()))],
                "score": round(0.2 + 0.4 * min((share - 50) / 40, 1) + 0.3 * KIND_WEIGHT["concentration"], 4),
            })
    return out


def _anomaly_findings(anoms: dict) -> list[dict]:
    out = []
    if anoms["spikes"]:
        s = anoms["spikes"][0]
        word = "spike" if s["direction"] == "spike" else "sudden dip"
        out.append({
            "id": f"spike:{s['measure']}|{s['t']}", "kind": "spike",
            "title": f"An unusual {word} in {fmt.humanize(s['measure'])} {fmt.when(s['t'], s['unit'])}",
            "columns": [s["measure"]], "stat": {"test": "Rolling-median residual (robust z)", "n": None},
            "details": s,
            "facts": [_fact(f"{fmt.title(s['measure'])} on {fmt.date(s['t'], s['unit'])}", s["value"]),
                      _fact("Typical level around that date", round(s["expected"], 2)),
                      _fact("Robust z-score", s["robust_z"])],
            "score": round(0.35 * min(abs(s["robust_z"]) / 10, 1) + 0.35 * min(s["rel_dev"] / 0.6, 1)
                           + 0.30 * KIND_WEIGHT["spike"], 4),
        })
    if anoms["points"]:
        p = anoms["points"][0]
        out.append({
            "id": f"anomaly:{p['column']}|{p['row']}", "kind": "anomaly",
            "title": f"One record stands far apart on {fmt.humanize(p['column'])}",
            "columns": [p["column"]], "stat": {"test": "Robust z-score (median/MAD)", "n": None},
            "details": {**p, "others": anoms["points"][1:6]},
            "facts": [_fact(f"{fmt.title(p['column'])} — {p['label']}", p["value"]),
                      _fact(f"Median {fmt.humanize(p['column'])}", p["median"]),
                      _fact("Robust z-score", p["robust_z"])],
            "score": round(0.55 * min(abs(p["robust_z"]) / 15, 1) + 0.30 * KIND_WEIGHT["anomaly"], 4),
        })
    return out


def extract(df: pd.DataFrame, schema: list[ColumnSchema], stats: dict, anomalies: dict) -> list[dict]:
    candidates = [_finding_from_test(t) for t in stats["tests"] if t["significant"]]
    # Near-identical measures (|r| > 0.98) are usually the same quantity in two units — not news.
    candidates = [f for f in candidates
                  if not (f["kind"] == "correlation" and abs(f["stat"]["effect"] or 0) > 0.98)]
    # Categories cut directly from a measure (non-overlapping ranges) restate the definition.
    candidates = [f for f in candidates
                  if not (f["kind"] == "group_difference" and f["details"].get("separable"))]
    candidates += _concentration(df, schema)
    candidates += _anomaly_findings(anomalies)
    candidates.sort(key=lambda f: -f["score"])

    chosen, usage = [], Counter()
    for f in candidates:
        if any(usage[c] >= 3 for c in f["columns"]):
            continue
        chosen.append(f)
        usage.update(f["columns"])
        if len(chosen) >= MAX_FINDINGS:
            break
    for rank, f in enumerate(chosen, 1):
        f["rank"] = rank
        for k in ("statistic", "p", "q", "effect", "effect_name", "magnitude", "n"):
            f["stat"].setdefault(k, None)
    return chosen
