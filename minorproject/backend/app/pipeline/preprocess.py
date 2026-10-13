"""Stage 2 — preprocessing: duplicates, missing values and outlier flagging.

Every change made to the data is recorded in an audit log so the final report can
say exactly what was done to the raw dataset.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .ingest import ColumnSchema

MAX_IMPUTE_FRACTION = 0.30   # impute numeric gaps only below this missing share
DROP_COLUMN_FRACTION = 0.60  # columns missing more than this are excluded from analysis


def preprocess(df: pd.DataFrame, schema: list[ColumnSchema]) -> tuple[pd.DataFrame, list[ColumnSchema], dict]:
    log: list[dict] = []
    n0 = len(df)
    out = df.copy()

    # Fully empty rows/columns.
    empty_cols = [c.name for c in schema if c.non_null == 0]
    if empty_cols:
        out = out.drop(columns=empty_cols)
        log.append({"action": "drop_columns", "columns": empty_cols, "reason": "entirely empty"})
    before = len(out)
    out = out.dropna(how="all")
    if len(out) < before:
        log.append({"action": "drop_rows", "count": before - len(out), "reason": "entirely empty rows"})

    # Exact duplicates.
    dup_mask = out.astype(str).duplicated()
    n_dups = int(dup_mask.sum())
    if n_dups:
        out = out[~dup_mask]
        log.append({"action": "drop_duplicates", "count": n_dups, "reason": "exact duplicate records"})

    kept_schema: list[ColumnSchema] = []
    excluded: list[str] = []
    imputed: dict[str, int] = {}
    outliers: dict[str, dict] = {}
    for c in schema:
        if c.name not in out.columns:
            continue
        s = out[c.name]
        miss = int(s.isna().sum())
        frac = miss / len(out) if len(out) else 0
        if frac > DROP_COLUMN_FRACTION and c.semantic != "id":
            excluded.append(c.name)
            log.append({"action": "exclude_column", "column": c.name,
                        "reason": f"{frac:.0%} missing — too sparse to analyse"})
            continue
        if c.semantic == "numeric":
            if 0 < frac <= MAX_IMPUTE_FRACTION:
                med = float(s.median())
                out[c.name] = s.fillna(med)
                imputed[c.name] = miss
                log.append({"action": "impute_median", "column": c.name, "count": miss,
                            "value": round(med, 4)})
            elif miss:
                log.append({"action": "keep_missing", "column": c.name, "count": miss,
                            "reason": f"{frac:.0%} missing — left as gaps rather than invented"})
            vals = out[c.name].dropna()
            if len(vals) >= 8:
                q1, q3 = np.percentile(vals, [25, 75])
                iqr = q3 - q1
                lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                n_out = int(((vals < lo) | (vals > hi)).sum())
                if n_out:
                    outliers[c.name] = {"count": n_out, "lower": float(lo), "upper": float(hi)}
        elif c.semantic in ("categorical", "boolean") and miss:
            out[c.name] = s.astype(object).where(s.notna(), "Unknown")
            imputed[c.name] = miss
            log.append({"action": "fill_unknown", "column": c.name, "count": miss})
        elif c.semantic == "datetime" and miss:
            before = len(out)
            out = out[out[c.name].notna()]
            if len(out) < before:
                log.append({"action": "drop_rows", "count": before - len(out),
                            "reason": f"missing timestamp in '{c.name}'"})
        kept_schema.append(c)

    if outliers:
        log.append({"action": "flag_outliers", "columns": {k: v["count"] for k, v in outliers.items()},
                    "reason": "IQR rule (1.5×IQR); flagged, not removed"})

    out = out.reset_index(drop=True)
    summary = {
        "rows_in": n0,
        "rows_out": len(out),
        "duplicates_removed": n_dups,
        "columns_excluded": excluded,
        "imputed": imputed,
        "outliers": outliers,
        "log": log,
    }
    return out, kept_schema, summary
