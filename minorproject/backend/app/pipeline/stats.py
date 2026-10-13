"""Stage 4 — statistical analysis.

Runs a family of descriptive and inferential tests over every sensible pair of
columns, then controls the false discovery rate across the *whole* family with
Benjamini–Hochberg so that the story is driven by findings that survive
multiple-comparison correction, not by whichever test happened to hit p < 0.05.

Tests:
  numeric × numeric        Pearson r (+ Spearman ρ as a robustness check)
  category × numeric       Welch t-test / one-way ANOVA, or Mann–Whitney / Kruskal–Wallis
                           when groups are small and non-normal; Cohen's d / η² effect sizes
  category × category      χ² test of independence with Cramér's V
  time × numeric           Kendall's τ trend test + OLS slope (statsmodels) on resampled series
"""
from __future__ import annotations

import itertools
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats as st
from statsmodels.stats.multitest import multipletests

from .ingest import ColumnSchema

MAX_TEST_ROWS = 100_000
MAX_LEVELS = 15
MIN_GROUP_N = 3


def _f(x) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(x) or np.isinf(x) else x


def magnitude(kind: str, effect: float | None) -> str:
    if effect is None:
        return "unknown"
    e = abs(effect)
    cuts = {
        "r": (0.1, 0.3, 0.5), "tau": (0.1, 0.3, 0.5), "cramers_v": (0.1, 0.3, 0.5),
        "d": (0.2, 0.5, 0.8), "eta2": (0.01, 0.06, 0.14),
    }[kind]
    labels = ("negligible", "weak", "moderate", "strong") if kind in ("r", "tau", "cramers_v") \
        else ("negligible", "small", "medium", "large")
    for cut, label in zip(cuts, labels):
        if e < cut:
            return label
    return labels[-1]


def analyse(df: pd.DataFrame, schema: list[ColumnSchema], time_axis: dict | None,
            alpha: float = 0.05, log=lambda *_: None) -> dict:
    data = df.sample(MAX_TEST_ROWS, random_state=11) if len(df) > MAX_TEST_ROWS else df
    numeric = [c.name for c in schema if c.semantic == "numeric" and data[c.name].nunique() > 2]
    cats = [c.name for c in schema if c.semantic in ("categorical", "boolean")
            and 2 <= data[c.name].astype(str).nunique() <= MAX_LEVELS]
    # Keep the test family tractable on wide datasets.
    numeric = sorted(numeric, key=lambda c: -data[c].notna().sum())[:14]
    cats = sorted(cats, key=lambda c: data[c].astype(str).nunique())[:8]

    normality = {}
    for c in numeric:
        v = data[c].dropna().astype(float)
        if len(v) >= 8 and v.std() > 0:
            sample = v.sample(min(len(v), 5000), random_state=3)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                w, p = st.shapiro(sample)
            normality[c] = {"W": _f(w), "p": _f(p), "normal": bool(p > 0.05)}

    tests: list[dict] = []
    tests += _correlations(data, numeric)
    log(f"Correlation tests: {len(tests)} numeric pairs")
    n0 = len(tests)
    tests += _group_tests(data, cats, numeric, normality)
    log(f"Group comparisons: {len(tests) - n0} category × measure pairs")
    n0 = len(tests)
    tests += _chi_square(data, cats)
    log(f"χ² independence tests: {len(tests) - n0} category pairs")
    n0 = len(tests)
    if time_axis:
        tests += _trends(df, time_axis, numeric)
        log(f"Trend tests over {time_axis['column']} by {time_axis['unit']}: {len(tests) - n0}")

    # Benjamini–Hochberg FDR control across the full family of tests.
    pvals = [t["p"] if t["p"] is not None else 1.0 for t in tests]
    if pvals:
        _, q, _, _ = multipletests(pvals, alpha=alpha, method="fdr_bh")
        for t, qv in zip(tests, q):
            t["q"] = _f(qv)
            t["significant"] = bool(qv < alpha and t["magnitude"] not in ("negligible", "unknown"))
    n_sig = sum(t["significant"] for t in tests)
    log(f"{len(tests)} tests run; {n_sig} significant after FDR correction (α={alpha})")

    return {
        "alpha": alpha,
        "n_tests": len(tests),
        "n_significant": n_sig,
        "normality": normality,
        "tests": tests,
        "correlation_matrix": _corr_matrix(data, numeric),
        "rows_tested": len(data),
    }


# ---------------------------------------------------------------------------- tests
def _correlations(df: pd.DataFrame, numeric: list[str]) -> list[dict]:
    out = []
    for a, b in itertools.combinations(numeric, 2):
        pair = df[[a, b]].dropna().astype(float)
        if len(pair) < 10 or pair[a].std() == 0 or pair[b].std() == 0:
            continue
        r, p = st.pearsonr(pair[a], pair[b])
        rho, p_s = st.spearmanr(pair[a], pair[b])
        slope, intercept = np.polyfit(pair[a], pair[b], 1)
        out.append({
            "id": f"corr:{a}|{b}", "kind": "correlation", "columns": [a, b],
            "test": "Pearson correlation", "statistic": _f(r), "p": _f(p),
            "effect": _f(r), "effect_name": "r", "magnitude": magnitude("r", r), "n": len(pair),
            "details": {"spearman_rho": _f(rho), "spearman_p": _f(p_s), "r2": _f(r * r),
                        "slope": _f(slope), "intercept": _f(intercept),
                        "direction": "positive" if r > 0 else "negative"},
        })
    return out


def _group_stats(v: pd.Series) -> dict:
    n = len(v)
    mean = v.mean()
    sd = v.std(ddof=1) if n > 1 else 0.0
    half = st.t.ppf(0.975, n - 1) * sd / np.sqrt(n) if n > 1 else 0.0
    return {"n": int(n), "mean": _f(mean), "median": _f(v.median()), "std": _f(sd),
            "ci_low": _f(mean - half), "ci_high": _f(mean + half), "min": _f(v.min()), "max": _f(v.max()),
            "p02": _f(v.quantile(0.02)), "p98": _f(v.quantile(0.98))}


def _separable(gstats: dict) -> bool:
    """True when the groups' core value ranges (2nd–98th percentile) don't overlap — the category is
    probably *defined* by the measure (e.g. Pass/Fail cut from a score), so the 'difference' is a
    tautology, not a finding."""
    ranges = sorted((g["p02"], g["p98"]) for g in gstats.values())
    return all(prev[1] <= nxt[0] for prev, nxt in zip(ranges, ranges[1:]))


def _group_tests(df: pd.DataFrame, cats: list[str], numeric: list[str], normality: dict) -> list[dict]:
    out = []
    for cat, num in itertools.product(cats, numeric):
        sub = df[[cat, num]].dropna()
        sub = sub.assign(**{cat: sub[cat].astype(str)})
        counts = sub[cat].value_counts()
        keep = counts[counts >= MIN_GROUP_N].index
        sub = sub[sub[cat].isin(keep)]
        if len(keep) < 2 or len(sub) < 10:
            continue
        groups = {k: g[num].astype(float) for k, g in sub.groupby(cat)}
        if all(g.std() == 0 for g in groups.values()):
            continue
        arrays = list(groups.values())
        parametric = all(len(g) >= 30 for g in arrays) or normality.get(num, {}).get("normal", False)
        gstats = {k: _group_stats(g) for k, g in groups.items()}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if len(arrays) == 2:
                a, b = arrays
                t, p_t = st.ttest_ind(a, b, equal_var=False)
                u, p_u = st.mannwhitneyu(a, b, alternative="two-sided")
                pooled = np.sqrt(((len(a) - 1) * a.var() + (len(b) - 1) * b.var()) / (len(a) + len(b) - 2))
                d = (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0
                test, stat, p = ("Welch t-test", t, p_t) if parametric else ("Mann–Whitney U", u, p_u)
                effect, ename = d, "d"
                alt = {"alt_test": "Mann–Whitney U" if parametric else "Welch t-test",
                       "alt_p": _f(p_u if parametric else p_t)}
            else:
                f, p_f = st.f_oneway(*arrays)
                h, p_h = st.kruskal(*arrays)
                grand = sub[num].astype(float).mean()
                ss_between = sum(len(g) * (g.mean() - grand) ** 2 for g in arrays)
                ss_total = ((sub[num].astype(float) - grand) ** 2).sum()
                eta2 = ss_between / ss_total if ss_total > 0 else 0.0
                test, stat, p = ("One-way ANOVA", f, p_f) if parametric else ("Kruskal–Wallis H", h, p_h)
                effect, ename = eta2, "eta2"
                alt = {"alt_test": "Kruskal–Wallis H" if parametric else "One-way ANOVA",
                       "alt_p": _f(p_h if parametric else p_f)}
        ranked = sorted(gstats.items(), key=lambda kv: -(kv[1]["mean"] or 0))
        out.append({
            "id": f"group:{cat}|{num}", "kind": "group_difference", "columns": [cat, num],
            "test": test, "statistic": _f(stat), "p": _f(p), "effect": _f(effect),
            "effect_name": ename, "magnitude": magnitude(ename, effect), "n": int(len(sub)),
            "details": {"groups": dict(ranked), "highest": ranked[0][0], "lowest": ranked[-1][0],
                        "ratio": _f(ranked[0][1]["mean"] / ranked[-1][1]["mean"])
                        if ranked[-1][1]["mean"] not in (0, None) else None,
                        "parametric": parametric, "separable": _separable(gstats), **alt},
        })
    return out


def _chi_square(df: pd.DataFrame, cats: list[str]) -> list[dict]:
    out = []
    for a, b in itertools.combinations(cats, 2):
        table = pd.crosstab(df[a].astype(str), df[b].astype(str))
        if table.shape[0] < 2 or table.shape[1] < 2 or table.values.sum() < 20:
            continue
        chi2, p, dof, expected = st.chi2_contingency(table)
        n = table.values.sum()
        k = min(table.shape) - 1
        v = np.sqrt(chi2 / (n * k)) if k > 0 else 0.0
        low_expected = float((expected < 5).mean())
        resid = (table - expected) / np.sqrt(expected)
        idx = np.unravel_index(np.argmax(resid.values), resid.shape)
        out.append({
            "id": f"chi2:{a}|{b}", "kind": "association", "columns": [a, b],
            "test": "χ² test of independence", "statistic": _f(chi2), "p": _f(p),
            "effect": _f(v), "effect_name": "cramers_v", "magnitude": magnitude("cramers_v", v),
            "n": int(n),
            "details": {"dof": int(dof), "low_expected_share": low_expected,
                        "strongest_cell": {"row": table.index[idx[0]], "col": table.columns[idx[1]],
                                           "observed": int(table.values[idx]),
                                           "expected": _f(expected[idx])},
                        "table": {"rows": table.index.tolist(), "cols": table.columns.tolist(),
                                  "values": table.values.tolist()}},
        })
    return out


def resample_series(df: pd.DataFrame, time_col: str, freq: str, value: str | None) -> pd.Series:
    s = df.dropna(subset=[time_col]).set_index(time_col).sort_index()
    if value is None:
        counts = s.resample(freq).size().astype(float)
        # Edge bins usually cover a partial period, which would fake a rise or fall.
        return counts.iloc[1:-1] if len(counts) >= 8 else counts
    return s[value].astype(float).resample(freq).mean().dropna()


def _trend_test(series: pd.Series) -> dict | None:
    series = series.dropna()
    if len(series) < 5 or series.std() == 0:
        return None
    x = np.arange(len(series), dtype=float)
    tau, p = st.kendalltau(x, series.values)
    model = sm.OLS(series.values, sm.add_constant(x)).fit()
    slope = float(model.params[1])
    first, last = float(series.iloc[0]), float(series.iloc[-1])
    return {"tau": _f(tau), "p": _f(p), "slope": slope, "slope_p": _f(model.pvalues[1]),
            "r2": _f(model.rsquared), "first": first, "last": last,
            "pct_change": _f((last - first) / abs(first) * 100) if first else None,
            "peak": {"t": series.idxmax().isoformat(), "v": _f(series.max())},
            "trough": {"t": series.idxmin().isoformat(), "v": _f(series.min())},
            "series": [{"t": t.isoformat(), "v": _f(v)} for t, v in series.items()]}


def _trends(df: pd.DataFrame, time_axis: dict, numeric: list[str]) -> list[dict]:
    out = []
    tcol, freq = time_axis["column"], time_axis["freq"]
    targets: list[str | None] = [None] + numeric
    for value in targets:
        try:
            series = resample_series(df[[tcol] + ([value] if value else [])], tcol, freq, value)
        except Exception:
            continue
        res = _trend_test(series)
        if not res:
            continue
        label = value or "record count"
        out.append({
            "id": f"trend:{tcol}|{label}", "kind": "trend", "columns": [tcol] + ([value] if value else []),
            "test": "Kendall τ trend test", "statistic": res["tau"], "p": res["p"],
            "effect": res["tau"], "effect_name": "tau", "magnitude": magnitude("tau", res["tau"]),
            "n": len(res["series"]),
            "details": {**res, "measure": label, "unit": time_axis["unit"],
                        "aggregation": "count of records" if value is None else "mean",
                        "direction": "rising" if (res["tau"] or 0) > 0 else "falling"},
        })
    return out


def _corr_matrix(df: pd.DataFrame, numeric: list[str]) -> dict | None:
    if len(numeric) < 2:
        return None
    m = df[numeric].astype(float).corr(method="pearson")
    return {"columns": numeric, "values": [[_f(v) for v in row] for row in m.values]}
