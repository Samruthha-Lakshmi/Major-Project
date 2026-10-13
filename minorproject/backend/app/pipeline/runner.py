"""Pipeline orchestrator — runs the eight stages in order and streams progress events."""
from __future__ import annotations

import time
import traceback
from datetime import datetime
from typing import Callable

import numpy as np
import pandas as pd

from . import eda, ingest, insights, narrative, preprocess, report, stats, viz
from .ingest import IngestError

Emit = Callable[[dict], None]


def _preview(df: pd.DataFrame, n: int = 8) -> dict:
    head = df.head(n).copy()
    for c in head.columns:
        if pd.api.types.is_datetime64_any_dtype(head[c]):
            head[c] = head[c].dt.strftime("%Y-%m-%d %H:%M").str.replace(" 00:00", "", regex=False)
    head = head.astype(object).where(head.notna(), None)
    rows = [[(round(v, 4) if isinstance(v, float) else (v.item() if isinstance(v, np.generic) else v))
             for v in r] for r in head.values.tolist()]
    return {"columns": [str(c) for c in df.columns], "rows": rows}


def _slim_tests(tests: list[dict]) -> list[dict]:
    """Keep full details only for significant tests so stored results stay small."""
    out = []
    for t in tests:
        if t.get("significant"):
            out.append(t)
        else:
            out.append({k: v for k, v in t.items() if k != "details"})
    return out


class StageTimer:
    def __init__(self, emit: Emit, stage: str):
        self.emit, self.stage = emit, stage

    def __enter__(self):
        self.t0 = time.perf_counter()
        self.emit({"type": "stage", "stage": self.stage, "status": "running"})
        return self

    def done(self, summary: dict | None = None):
        ms = int((time.perf_counter() - self.t0) * 1000)
        self.emit({"type": "stage", "stage": self.stage, "status": "done", "ms": ms, "summary": summary or {}})

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            self.emit({"type": "stage", "stage": self.stage, "status": "error", "message": str(exc)})
        return False


def run(run_id: str, loader: Callable[[Callable], tuple[pd.DataFrame, dict]], options: dict,
        emit: Emit) -> tuple[dict, str]:
    """Execute the full pipeline. *loader(log)* returns (raw_df, source_meta)."""
    t_start = time.perf_counter()
    created = datetime.now().isoformat(timespec="seconds")
    alpha = float(options.get("alpha", 0.05))
    mode = options.get("narrative_mode", "template")
    current = {"stage": "ingest"}

    def log(message: str, level: str = "info"):
        emit({"type": "log", "level": level, "stage": current["stage"], "message": message})

    # 1 — ingestion & validation ------------------------------------------------
    with StageTimer(emit, "ingest") as st:
        raw, source = loader(log)
        log(f"Loaded {len(raw):,} rows × {raw.shape[1]} columns from {source['name']}")
        typed, schema = ingest.infer_schema(raw)
        counts = pd.Series([c.semantic for c in schema]).value_counts().to_dict()
        log("Inferred types: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
        issues = ingest.validate(typed, schema)
        for i in issues:
            log(i["message"], "warning" if i["level"] != "info" else "info")
        if any(i["level"] == "error" for i in issues):
            raise IngestError(next(i["message"] for i in issues if i["level"] == "error"))
        emit({"type": "preview", **_preview(raw)})
        ingest_out = {"rows": len(raw), "cols": raw.shape[1], "schema": [c.to_dict() for c in schema],
                      "issues": issues, "type_counts": counts}
        st.done({"rows": len(raw), "cols": raw.shape[1], "types": counts, "issues": len(issues),
                 "schema": [{"name": c.name, "semantic": c.semantic, "missing": c.missing} for c in schema]})

    # 2 — preprocessing -------------------------------------------------------------
    current["stage"] = "preprocess"
    with StageTimer(emit, "preprocess") as st:
        clean, schema, pre = preprocess.preprocess(typed, schema)
        for entry in pre["log"]:
            log(_describe(entry))
        st.done({"rows_out": pre["rows_out"], "duplicates": pre["duplicates_removed"],
                 "imputed": sum(pre["imputed"].values()), "outlier_cols": len(pre["outliers"]),
                 "excluded": len(pre["columns_excluded"])})

    # 3 — EDA ----------------------------------------------------------------------
    current["stage"] = "eda"
    with StageTimer(emit, "eda") as st:
        prof = eda.profile(clean, schema)
        prof["rows"] = len(clean)
        ta = prof["time_axis"]
        if ta:
            log(f"Time axis: '{ta['column']}' spanning {ta['span_days']:.0f} days → resampled by {ta['unit']}")
        else:
            log("No usable time axis — trend analysis skipped")
        numeric_cols = [k for k, v in prof["columns"].items() if v["semantic"] == "numeric"]
        st.done({"numeric": len(numeric_cols), "time_axis": ta["column"] if ta else None,
                 "unit": ta["unit"] if ta else None,
                 "distributions": {k: prof["columns"][k].get("histogram") for k in numeric_cols[:6]}})

    # 4 — statistics ---------------------------------------------------------------
    current["stage"] = "stats"
    with StageTimer(emit, "stats") as st:
        s = stats.analyse(clean, schema, ta, alpha=alpha, log=log)
        top = sorted([t for t in s["tests"] if t["significant"]], key=lambda t: 1.0 if t["q"] is None else t["q"])[:6]
        st.done({"n_tests": s["n_tests"], "n_significant": s["n_significant"], "alpha": alpha,
                 "by_kind": pd.Series([t["kind"] for t in s["tests"]]).value_counts().to_dict() if s["tests"] else {},
                 "top": [{"id": t["id"], "test": t["test"], "columns": t["columns"], "q": t["q"],
                          "effect": t["effect"], "effect_name": t["effect_name"], "magnitude": t["magnitude"]}
                         for t in top]})

    # 5 — insights & anomalies -----------------------------------------------------
    current["stage"] = "insights"
    with StageTimer(emit, "insights") as st:
        anomalies = insights.detect_anomalies(clean, schema, ta, pre["outliers"])
        log(f"Anomalies: {len(anomalies['points'])} extreme values, {len(anomalies['multivariate'])} "
            f"multivariate outliers, {len(anomalies['spikes'])} time-series spikes")
        findings = insights.extract(clean, schema, s, anomalies)
        for f in findings:
            emit({"type": "finding", "finding": f})
        log(f"{len(findings)} findings selected for the story")
        st.done({"findings": len(findings), "points": len(anomalies["points"]),
                 "multivariate": len(anomalies["multivariate"]), "spikes": len(anomalies["spikes"])})

    # 6 — visualization ------------------------------------------------------------
    current["stage"] = "viz"
    with StageTimer(emit, "viz") as st:
        kinds = {}
        for f in findings:
            try:
                f["chart"] = viz.build_chart(f, clean, ta)
                kinds[f["chart"]["type"]] = kinds.get(f["chart"]["type"], 0) + 1
                emit({"type": "chart", "finding_id": f["id"], "chart": f["chart"]})
                log(f"{f['chart']['type'].title()} chart for “{f['title']}”")
            except Exception as exc:
                f["chart"] = None
                log(f"Chart failed for {f['id']}: {exc}", "warning")
        overview = viz.overview_charts(prof, s)
        st.done({"charts": len([f for f in findings if f.get("chart")]) + len(overview), "types": kinds})

    # 7 — narrative ----------------------------------------------------------------
    current["stage"] = "narrative"
    with StageTimer(emit, "narrative") as st:
        ctx = {"source_name": source["name"], "description": source.get("description", ""),
               "rows": len(clean), "n_tests": s["n_tests"], "n_significant": s["n_significant"],
               "alpha": alpha, "preprocess": pre, "columns": [c.name for c in schema]}
        story = narrative.generate(ctx, findings, mode,
                                   on_delta=lambda d: emit({"type": "narrative_delta", "text": d}), log=log)
        emit({"type": "story", "story": story})
        st.done({"engine": story["engine"], "sections": len(story["sections"]),
                 "verification": story.get("verification", {}).get("verified")})

    # 8 — report -------------------------------------------------------------------
    current["stage"] = "report"
    with StageTimer(emit, "report") as st:
        result = {
            "run_id": run_id, "created_at": created, "source": source,
            "options": {"narrative_mode": mode, "alpha": alpha},
            "ingest": ingest_out, "preprocess": pre, "profile": prof,
            "stats": {**s, "tests": _slim_tests(s["tests"])},
            "anomalies": anomalies, "findings": findings, "overview_charts": overview, "story": story,
            "preview": _preview(raw, 25),
        }
        result["duration_ms"] = int((time.perf_counter() - t_start) * 1000)
        html = report.render(result)
        log(f"Report assembled — {len(html) / 1024:.0f} KB of HTML")
        st.done({"bytes": len(html)})
    result["duration_ms"] = int((time.perf_counter() - t_start) * 1000)
    return result, html


def _describe(e: dict) -> str:
    a = e["action"]
    if a == "drop_columns":
        return f"Dropped empty columns: {', '.join(e['columns'])}"
    if a == "drop_rows":
        return f"Dropped {e['count']:,} rows ({e['reason']})"
    if a == "drop_duplicates":
        return f"Removed {e['count']:,} duplicate records"
    if a == "exclude_column":
        return f"Excluded '{e['column']}' — {e['reason']}"
    if a == "impute_median":
        return f"Imputed {e['count']:,} missing '{e['column']}' values with median {e['value']}"
    if a == "keep_missing":
        return f"Kept {e['count']:,} gaps in '{e['column']}' — {e['reason']}"
    if a == "fill_unknown":
        return f"Labelled {e['count']:,} missing '{e['column']}' values as 'Unknown'"
    if a == "flag_outliers":
        return "Flagged outliers (kept): " + ", ".join(f"{k} ({v})" for k, v in e["columns"].items())
    return str(e)


def format_error(exc: Exception) -> str:
    from ..sources.live import SourceError
    if isinstance(exc, (IngestError, SourceError)):
        return str(exc)
    return f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}"
