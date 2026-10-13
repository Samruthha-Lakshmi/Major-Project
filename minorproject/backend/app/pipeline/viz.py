"""Stage 6 — visualization recommendation.

Picks the chart type that suits each finding (and says why), then builds it as a
Plotly figure. Figures are emitted as JSON so the same spec renders in the live
UI (plotly.js) and inside the standalone HTML report.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

from . import fmt

INK = "#14161a"
ACCENT = "#ff5a36"
TEAL = "#1fb5a8"
PALETTE = ["#ff5a36", "#1fb5a8", "#f2b134", "#6b8afd", "#c46bff", "#47c97a", "#ff8fb1", "#8ea0b6"]
MAX_POINTS = 2500


def _base_layout(title: str, xlab: str = "", ylab: str = "") -> dict:
    return dict(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=15)),
        margin=dict(l=56, r=20, t=48, b=48),
        font=dict(family="Inter, system-ui, sans-serif", size=12),
        xaxis=dict(title=xlab, showgrid=False, zeroline=False),
        yaxis=dict(title=ylab, gridcolor="rgba(128,128,128,0.18)", zeroline=False),
        legend=dict(orientation="h", y=-0.2),
        hoverlabel=dict(font=dict(family="JetBrains Mono, monospace")),
        colorway=PALETTE, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )


def _to_json(fig: go.Figure) -> dict:
    return json.loads(json.dumps(fig.to_plotly_json(), cls=PlotlyJSONEncoder))


def _trend(f: dict) -> tuple[go.Figure, str]:
    d = f["details"]
    xs = [p["t"] for p in d["series"]]
    ys = [p["v"] for p in d["series"]]
    x_idx = np.arange(len(ys))
    fit = d["slope"] * x_idx + (np.mean(ys) - d["slope"] * x_idx.mean())
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=fmt.label(d["measure"]),
                             line=dict(color=ACCENT, width=2.5), marker=dict(size=5),
                             fill="tozeroy", fillcolor="rgba(255,90,54,0.08)"))
    fig.add_trace(go.Scatter(x=xs, y=fit, mode="lines", name="Linear trend",
                             line=dict(color=TEAL, width=1.5, dash="dash")))
    fig.add_annotation(x=d["peak"]["t"], y=d["peak"]["v"], text=f"Peak {fmt.num(d['peak']['v'])}",
                       showarrow=True, arrowhead=0, ay=-30, font=dict(size=11))
    layout = _base_layout(f["title"], d["unit"].title(), fmt.label(d["measure"]))
    layout["showlegend"] = True
    fig.update_layout(**layout)
    return fig, "Line chart — a change over an ordered time axis reads best as a continuous line; the dashed line is the fitted OLS trend."


def _correlation(f: dict, df: pd.DataFrame) -> tuple[go.Figure, str]:
    a, b = f["columns"]
    pair = df[[a, b]].dropna()
    if len(pair) > MAX_POINTS:
        pair = pair.sample(MAX_POINTS, random_state=1)
    d = f["details"]
    xs = np.linspace(pair[a].min(), pair[a].max(), 50)
    fig = go.Figure()
    fig.add_trace(go.Scattergl(x=pair[a], y=pair[b], mode="markers",
                               marker=dict(color=ACCENT, size=6, opacity=0.55), name="Records"))
    fig.add_trace(go.Scatter(x=xs, y=d["slope"] * xs + d["intercept"], mode="lines",
                             line=dict(color=TEAL, width=2), name="Best fit"))
    fig.update_layout(**_base_layout(f["title"], fmt.label(a), fmt.label(b)))
    return fig, "Scatter plot with fitted line — the honest way to show how two measures co-vary record by record."


def _group(f: dict) -> tuple[go.Figure, str]:
    cat, measure = f["columns"]
    g = f["details"]["groups"]
    names = list(g)[:15]
    means = [g[k]["mean"] for k in names]
    err_hi = [g[k]["ci_high"] - g[k]["mean"] for k in names]
    err_lo = [g[k]["mean"] - g[k]["ci_low"] for k in names]
    colors = [ACCENT if i == 0 else ("#8ea0b6" if i < len(names) - 1 else TEAL) for i in range(len(names))]
    horizontal = len(names) > 6 or max(len(str(n)) for n in names) > 12
    bar = go.Bar(
        x=means if horizontal else names, y=names if horizontal else means,
        orientation="h" if horizontal else "v", marker_color=colors,
        error_x=dict(type="data", array=err_hi, arrayminus=err_lo, color="#8a8f98") if horizontal else None,
        error_y=None if horizontal else dict(type="data", array=err_hi, arrayminus=err_lo, color="#8a8f98"),
        customdata=[g[k]["n"] for k in names],
        hovertemplate="%{y}: %{x:,.3g}<br>n=%{customdata}<extra></extra>" if horizontal
        else "%{x}: %{y:,.3g}<br>n=%{customdata}<extra></extra>")
    fig = go.Figure(bar)
    layout = _base_layout(f["title"], f"Average {fmt.humanize(measure)}" if horizontal else fmt.title(cat),
                          fmt.title(cat) if horizontal else f"Average {fmt.humanize(measure)}")
    if horizontal:
        layout["yaxis"]["autorange"] = "reversed"
        layout["margin"]["l"] = 140
    fig.update_layout(**layout)
    return fig, "Ranked bar chart of group means with 95% confidence intervals — compares categories directly and shows the uncertainty."


def _association(f: dict) -> tuple[go.Figure, str]:
    t = f["details"]["table"]
    vals = np.array(t["values"], dtype=float)
    share = vals / vals.sum(axis=1, keepdims=True) * 100
    fig = go.Figure(go.Heatmap(z=share, x=t["cols"], y=t["rows"], colorscale=[[0, "rgba(31,181,168,0.05)"], [1, ACCENT]],
                               text=np.round(share, 1), texttemplate="%{text}%", hovertemplate="%{y} × %{x}: %{z:.1f}%<extra></extra>",
                               colorbar=dict(title="% of row")))
    a, b = f["columns"]
    fig.update_layout(**_base_layout(f["title"], fmt.title(b), fmt.title(a)))
    return fig, "Heatmap of row percentages — shows where the two categories over- or under-lap compared with an even mix."


def _spike(f: dict, df: pd.DataFrame, time_axis: dict | None) -> tuple[go.Figure, str]:
    from .stats import resample_series
    d = f["details"]
    measure = None if d["measure"] == "record count" else d["measure"]
    cols = [time_axis["column"]] + ([measure] if measure else [])
    series = resample_series(df[cols], time_axis["column"], time_axis["freq"], measure)
    fig = go.Figure(go.Scatter(x=series.index, y=series.values, mode="lines", line=dict(color="#8ea0b6", width=2)))
    fig.add_trace(go.Scatter(x=[d["t"]], y=[d["value"]], mode="markers",
                             marker=dict(color=ACCENT, size=14, line=dict(color="white", width=2))))
    fig.update_layout(**_base_layout(f["title"], d["unit"].title(), fmt.label(d["measure"])))
    return fig, "Line chart with the anomalous period highlighted — context first, then the outlier."


def _anomaly(f: dict, df: pd.DataFrame) -> tuple[go.Figure, str]:
    d = f["details"]
    col = d["column"]
    v = df[col].dropna()
    flagged = {d["row"]} | {o["row"] for o in d.get("others", []) if o["column"] == col}
    fig = go.Figure(go.Box(x=v.values, boxpoints="outliers", marker=dict(color="#8ea0b6", size=5),
                           line=dict(color="#8ea0b6"), name=""))
    fx = [df.at[i, col] for i in flagged if i in df.index]
    fig.add_trace(go.Scatter(x=fx, y=[""] * len(fx), mode="markers",
                             marker=dict(color=ACCENT, size=13, symbol="diamond", line=dict(color="white", width=1.5)),
                             hovertemplate="%{x}<extra>flagged</extra>"))
    fig.update_layout(**_base_layout(f["title"], fmt.label(col), ""))
    return fig, "Box plot with flagged records — shows the typical range so the outlier's distance is obvious."


def _concentration(f: dict, df: pd.DataFrame) -> tuple[go.Figure, str]:
    col = f["columns"][0]
    v = np.sort(df[col].dropna().astype(float).values)[::-1]
    cum = np.cumsum(v) / v.sum() * 100
    x = np.arange(1, len(v) + 1) / len(v) * 100
    step = max(1, len(v) // 400)
    fig = go.Figure(go.Scatter(x=x[::step], y=cum[::step], mode="lines", line=dict(color=ACCENT, width=2.5),
                               fill="tozeroy", fillcolor="rgba(255,90,54,0.08)"))
    fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", line=dict(color="#8ea0b6", dash="dot")))
    fig.add_vline(x=10, line=dict(color=TEAL, dash="dash"))
    fig.update_layout(**_base_layout(f["title"], "% of records (largest first)", f"Cumulative % of {fmt.humanize(col)}"))
    return fig, "Concentration (Lorenz-style) curve — the further it bows above the diagonal, the more unequal the distribution."


def build_chart(f: dict, df: pd.DataFrame, time_axis: dict | None) -> dict:
    kind = f["kind"]
    if kind == "trend":
        fig, why = _trend(f)
    elif kind == "correlation":
        fig, why = _correlation(f, df)
    elif kind == "group_difference":
        fig, why = _group(f)
    elif kind == "association":
        fig, why = _association(f)
    elif kind == "spike" and time_axis:
        fig, why = _spike(f, df, time_axis)
    elif kind == "anomaly":
        fig, why = _anomaly(f, df)
    elif kind == "concentration":
        fig, why = _concentration(f, df)
    else:
        raise ValueError(f"no chart for {kind}")
    chart_type = {"trend": "line", "correlation": "scatter", "group_difference": "bar",
                  "association": "heatmap", "spike": "line", "anomaly": "box",
                  "concentration": "lorenz"}[kind]
    return {"type": chart_type, "reason": why, "figure": _to_json(fig)}


def overview_charts(eda: dict, stats: dict) -> list[dict]:
    charts = []
    cm = stats.get("correlation_matrix")
    if cm and len(cm["columns"]) >= 3:
        fig = go.Figure(go.Heatmap(z=cm["values"], x=[fmt.title(c) for c in cm["columns"]],
                                   y=[fmt.title(c) for c in cm["columns"]], zmin=-1, zmax=1,
                                   colorscale=[[0, TEAL], [0.5, "rgba(128,128,128,0.08)"], [1, ACCENT]],
                                   hovertemplate="%{y} × %{x}: r = %{z:.2f}<extra></extra>"))
        layout = _base_layout("How every measure relates to every other")
        layout["margin"]["l"] = 120
        fig.update_layout(**layout)
        charts.append({"id": "overview:corr", "type": "heatmap", "figure": _to_json(fig),
                       "reason": "Correlation matrix — a one-glance map of which measures move together."})
    return charts
