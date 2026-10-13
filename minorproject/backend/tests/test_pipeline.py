import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline import eda, fmt, ingest, insights, narrative, preprocess, runner, stats  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"


def _csv(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()


def test_type_inference():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60).strftime("%Y-%m-%d"),
        "price": [f"${x:,.2f}" for x in np.linspace(10, 2000, 60)],
        "region": ["North", "South", "East"] * 20,
        "flag": ["Yes", "No"] * 30,
        "order_id": range(1000, 1060),
    })
    typed, schema = ingest.infer_schema(ingest.load_bytes("x.csv", _csv(df)))
    kinds = {c.name: c.semantic for c in schema}
    assert kinds == {"date": "datetime", "price": "numeric", "region": "categorical",
                     "flag": "boolean", "order_id": "id"}
    assert typed["price"].iloc[-1] == pytest.approx(2000)


def test_semicolon_and_json_loading():
    df = ingest.load_bytes("a.csv", b"a;b\n1;2\n3;4\n")
    assert list(df.columns) == ["a", "b"]
    df = ingest.load_bytes("a.json", json.dumps({"data": [{"x": 1}, {"x": 2}]}).encode())
    assert df["x"].tolist() == [1, 2]


def test_preprocess_duplicates_and_imputation():
    df = pd.DataFrame({"v": [1.0, 2.0, np.nan, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0] * 3,
                       "g": list("ab") * 15})
    df = pd.concat([df, df.iloc[:2]])
    typed, schema = ingest.infer_schema(df)
    clean, _, summary = preprocess.preprocess(typed, schema)
    assert summary["duplicates_removed"] > 0
    assert clean["v"].isna().sum() == 0


def test_stats_find_planted_effects():
    rng = np.random.default_rng(0)
    n = 400
    g = rng.choice(["A", "B"], n)
    x = rng.normal(0, 1, n)
    y = 2 * x + rng.normal(0, 1, n) + (g == "A") * 1.5
    noise = rng.normal(0, 1, n)
    df = pd.DataFrame({"g": g, "x": x, "y": y, "noise": noise})
    typed, schema = ingest.infer_schema(df)
    res = stats.analyse(typed, schema, None)
    sig = {t["id"] for t in res["tests"] if t["significant"]}
    assert "corr:x|y" in sig and "group:g|y" in sig
    assert "corr:x|noise" not in sig and "group:g|noise" not in sig


def test_trend_detection():
    dates = pd.date_range("2020-01-01", periods=48, freq="MS")
    df = pd.DataFrame({"month": dates, "sales": np.arange(48) * 3.0 + np.random.default_rng(1).normal(0, 4, 48)})
    typed, schema = ingest.infer_schema(df)
    ta = eda.pick_time_axis(typed, schema)
    assert ta["unit"] == "month"
    res = stats.analyse(typed, schema, ta)
    trend = next(t for t in res["tests"] if t["kind"] == "trend" and "sales" in t["columns"])
    assert trend["significant"] and trend["details"]["direction"] == "rising"


def test_fact_check_rejects_invented_numbers():
    allowed = [70.33, 46.01, 1400.0, 0.62, 38.7]
    assert narrative.verify_text("Scores averaged 70.33 against 46.01 across 1,400 students.", allowed) == []
    assert narrative.verify_text("About 38.7% of variation; r = 0.62.", allowed) == []
    assert narrative.verify_text("Scores rose by 83% to 912.4 points.", allowed) == ["83%", "912.4"]


def test_humanize():
    assert fmt.humanize("pm25_ugm3") == "PM2.5"
    assert fmt.label("temperature_c") == "Temperature (°C)"
    assert fmt.humanize("studyHoursPerDay") == "study hours per day"


@pytest.mark.parametrize("name", ["student_performance.csv", "city_air_quality.csv", "retail_sales.csv"])
def test_end_to_end_on_samples(name):
    path = SAMPLES / name
    if not path.exists():
        pytest.skip("run scripts/make_samples.py first")
    events = []
    result, html = runner.run("test", lambda log: (ingest.load_bytes(name, path.read_bytes()), {"type": "sample", "name": name}),
                              {"narrative_mode": "template", "alpha": 0.05}, events.append)
    stages_done = [e["stage"] for e in events if e["type"] == "stage" and e["status"] == "done"]
    assert stages_done == ["ingest", "preprocess", "eda", "stats", "insights", "viz", "narrative", "report"]
    assert result["findings"], "expected at least one finding"
    assert all(f.get("chart") for f in result["findings"])
    assert result["story"]["headline"] in html
    # Every number the template engine writes must pass its own fact-check.
    allowed = narrative.allowed_numbers({"rows": result["profile"]["rows"], "n_tests": result["stats"]["n_tests"],
                                         "n_significant": result["stats"]["n_significant"], "alpha": 0.05,
                                         "preprocess": result["preprocess"], "source_name": name},
                                        result["findings"])
    for sec in result["story"]["sections"]:
        assert narrative.verify_text(sec["body"], allowed) == [], sec["body"]
    from app import jsonutil
    json.loads(jsonutil.dumps(result))


def test_ai_narrative_fact_check_with_fake_model(monkeypatch):
    """Drive the Claude path with a fake stream: verified passages are kept, an invented number is replaced."""
    import anthropic

    path = SAMPLES / "student_performance.csv"
    if not path.exists():
        pytest.skip("run scripts/make_samples.py first")
    result, _ = runner.run("t", lambda log: (ingest.load_bytes(path.name, path.read_bytes()), {"type": "sample", "name": "students"}),
                           {"narrative_mode": "template", "alpha": 0.05}, lambda e: None)
    findings = result["findings"]
    f0, f1 = findings[0], findings[1]
    true_number = f0["facts"][0]["display"]
    text = (f"HEADLINE: Study habits shape exam results\nSTANDFIRST: An analysis of {result['profile']['rows']:,} students.\n"
            f"LEDE: The clearest pattern involves {true_number}.\n"
            f"### F1 | Honest section\nThe figure was {true_number}.\n"
            f"### F2 | Invented section\nScores jumped by 731.9 points.\n")

    class FakeStream:
        text_stream = iter([text[:40], text[40:]])

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return type("M", (), {"stop_reason": "end_turn", "model": "fake-model"})()

    class FakeClient:
        def __init__(self, *a, **k):
            self.beta = type("B", (), {"messages": type("Ms", (), {"stream": lambda self, **kw: FakeStream()})()})()

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    ctx = {"source_name": "students", "rows": result["profile"]["rows"], "n_tests": result["stats"]["n_tests"],
           "n_significant": result["stats"]["n_significant"], "alpha": 0.05, "preprocess": result["preprocess"],
           "columns": []}
    deltas = []
    story = narrative.ai_story(ctx, findings, deltas.append, lambda *a: None)
    assert "".join(deltas) == text
    assert story["engine"] == "ai" and story["headline"] == "Study habits shape exam results"
    by_id = {s["finding_id"]: s for s in story["sections"]}
    assert by_id[f0["id"]]["body"] == f"The figure was {true_number}."
    assert "731.9" not in by_id[f1["id"]]["body"]          # replaced by the template version
    bad = [d for d in story["verification"]["details"] if d["status"] == "unverified"]
    assert bad and bad[0]["numbers"] == ["731.9"]
