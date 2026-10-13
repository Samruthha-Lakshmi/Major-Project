"""Stage 8 — HTML report generation with Jinja2.

Produces one self-contained, responsive news article. Charts are embedded as
Plotly JSON and rendered with plotly.js — from the CDN by default, or inlined
for a fully offline file.
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from plotly.offline import get_plotlyjs, get_plotlyjs_version

from . import fmt

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "j2"]))
_env.filters["num"] = fmt.num
_env.filters["pct"] = fmt.pct
_env.filters["pval"] = fmt.pval
_env.filters["human"] = fmt.humanize
_env.filters["title_case"] = fmt.title


@lru_cache(maxsize=1)
def _inline_plotly() -> str:
    return get_plotlyjs()


def render(result: dict, offline: bool = False) -> str:
    findings = result["findings"]
    story = result["story"]
    sections = {s["finding_id"]: s for s in story["sections"]}
    charts = {f["id"]: f.get("chart") for f in findings}
    created = datetime.fromisoformat(result["created_at"])
    key_numbers = []
    for f in findings[:4]:
        fact = next((x for x in f["facts"] if x["label"] not in ("Observations",)), None)
        if fact:
            key_numbers.append({"value": fact["display"], "label": fact["label"], "finding": f["title"]})
    return _env.get_template("report.html.j2").render(
        r=result, story=story, findings=findings, sections=sections,
        chart_json=json.dumps({k: v["figure"] for k, v in charts.items() if v}),
        overview_json=json.dumps([c["figure"] for c in result.get("overview_charts", [])]),
        key_numbers=key_numbers,
        dateline=created.strftime("%d %B %Y, %H:%M").lstrip("0"),
        plotly_inline=_inline_plotly() if offline else None,
        plotly_cdn=f"https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js",
        fmt=fmt,
    )
