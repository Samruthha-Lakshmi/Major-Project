"""Stage 7 — narrative generation.

Two engines share one contract — every number in the copy must come from a
validated finding:

* ``template``: deterministic natural-language templates driven directly by
  the statistical results. Always available, fully reproducible.
* ``ai``: Claude rewrites the findings as a news story, streaming live to the
  UI. Its output is then *fact-checked*: every number it writes is matched
  against the verified facts, and any section containing an unverifiable
  number is replaced by the template version (and the swap is logged).
"""
from __future__ import annotations

import json
import re
from typing import Callable

from . import fmt
from ..config import ANTHROPIC_MODEL, llm_available

# ---------------------------------------------------------------------------- templates


def _sig_clause(stat: dict) -> str:
    q = stat.get("q")
    qs = f", FDR-adjusted q = {q:.3g}" if q is not None and q >= 0.001 else (", q < 0.001" if q is not None else "")
    return f"{fmt.pval(stat.get('p'))}{qs}"


def finding_text(f: dict, ctx: dict) -> str:
    d, s, kind = f["details"], f["stat"], f["kind"]
    if kind == "trend":
        unit, series = d["unit"], d["series"]
        subject = (f"The number of records per {unit}" if d["measure"] == "record count"
                   else f"Average {fmt.humanize(d['measure'])} per {unit}")
        move = "risen" if d["direction"] == "rising" else "fallen"
        change = f" — a change of {fmt.pct(d['pct_change'], True)}" if d.get("pct_change") is not None else ""
        return (f"{subject} has {move} across the {len(series)} {unit}s covered by the data, from "
                f"{fmt.num(d['first'])} in {fmt.date(series[0]['t'], unit)} to {fmt.num(d['last'])} in "
                f"{fmt.date(series[-1]['t'], unit)}{change}. The highest level came in "
                f"{fmt.date(d['peak']['t'], unit)}, at {fmt.num(d['peak']['v'])}. A Kendall trend test rates the "
                f"movement as {s['magnitude']} (τ = {s['effect']:.2f}) and statistically significant "
                f"({_sig_clause(s)}), so it is unlikely to be random fluctuation.")
    if kind == "group_difference":
        cat, measure = f["columns"]
        g, hi, lo = d["groups"], d["highest"], d["lowest"]
        ratio = (f" — {d['ratio']:.2f} times as much" if d.get("ratio") and d["ratio"] >= 1.15 else "")
        binary = {hi, lo} <= {"Yes", "No", "True", "False"}
        name = (lambda v: f"records where {fmt.humanize(cat)} is '{v}'") if binary else (lambda v: v)
        groups = (f"the {len(g)} {fmt.humanize(cat)} groups" if len(g) > 2
                  else f"{fmt.humanize(cat)} groups" if binary else f"{hi} and {lo}")
        ename = {"d": "Cohen's d", "eta2": "η²"}[s["effect_name"]]
        lead = name(hi)
        lead = lead[:1].upper() + lead[1:]
        verb = "show" if binary else "records"
        return (f"Average {fmt.humanize(measure)} is far from uniform across {groups}. {lead} {verb} the "
                f"highest average, {fmt.num(g[hi]['mean'])} (n = {g[hi]['n']:,}), against {fmt.num(g[lo]['mean'])} "
                f"for {name(lo)} (n = {g[lo]['n']:,}){ratio}. A {s['test']} indicates the gap is very unlikely to be "
                f"chance ({_sig_clause(s)}), and the effect is {s['magnitude']} ({ename} = {abs(s['effect']):.2f}).")
    if kind == "correlation":
        a, b = f["columns"]
        more = "higher" if d["direction"] == "positive" else "lower"
        return (f"Records with higher {fmt.humanize(a)} tend to have {more} {fmt.humanize(b)}. The relationship "
                f"is {s['magnitude']} (Pearson r = {s['effect']:.2f}, n = {s['n']:,}; {_sig_clause(s)}), meaning "
                f"{fmt.humanize(a)} accounts for about {fmt.pct(d['r2'] * 100)} of the variation in "
                f"{fmt.humanize(b)}. A rank-based check agrees (Spearman ρ = {d['spearman_rho']:.2f}). "
                f"This is an association in observational data, not proof that one causes the other.")
    if kind == "association":
        a, b = f["columns"]
        c = d["strongest_cell"]
        caveat = (" Some cells are sparse, so the exact strength should be read with care."
                  if d["low_expected_share"] > 0.2 else "")
        return (f"{fmt.title(a)} and {fmt.humanize(b)} are not independent of each other. The combination "
                f"'{c['row']}' with '{c['col']}' appears {c['observed']:,} times, against roughly "
                f"{fmt.num(c['expected'])} if the two were unrelated. A χ² test confirms the link "
                f"({_sig_clause(s)}; Cramér's V = {s['effect']:.2f}, a {s['magnitude']} association).{caveat}")
    if kind == "spike":
        word = "jumped" if d["direction"] == "spike" else "dropped"
        subject = "The number of records" if d["measure"] == "record count" else fmt.title(d["measure"])
        return (f"{subject} {word} to {fmt.num(d['value'])} {fmt.when(d['t'], d['unit'])}, far from the "
                f"typical level of around {fmt.num(d['expected'])} in the surrounding {d['unit']}s "
                f"(robust z = {d['robust_z']:.1f}). Unusual movements like this are worth checking against "
                f"events on the ground before drawing conclusions.")
    if kind == "anomaly":
        others = [o for o in d.get("others", []) if o["column"] == d["column"]][:3]
        tail = ""
        if others:
            tail = " Other extreme values include " + "; ".join(
                f"{o['label']} ({fmt.num(o['value'])})" for o in others) + "."
        return (f"{d['label']} stands out with a {fmt.humanize(d['column'])} of {fmt.num(d['value'])}, "
                f"compared with a median of {fmt.num(d['median'])} across all records (robust z = "
                f"{d['robust_z']:.1f}). A value this extreme may be genuine or a recording error, and should "
                f"be verified with the data source before publication.{tail}")
    if kind == "concentration":
        return (f"The distribution of {fmt.humanize(f['columns'][0])} is highly unequal: the top 10% of "
                f"records ({d['k']:,} of {d['n']:,}) account for {fmt.pct(d['share_top10'])} of the total "
                f"{fmt.num(d['total'])}.")
    return ""


def _caveats(ctx: dict, findings: list[dict]) -> list[str]:
    out = []
    pre = ctx["preprocess"]
    if pre["imputed"]:
        cols = ", ".join(fmt.humanize(c) for c in list(pre["imputed"])[:4])
        out.append(f"Missing values were filled in for {cols} (median for measures, 'Unknown' for categories).")
    if pre["columns_excluded"]:
        out.append("Columns too sparse to analyse were excluded: "
                   + ", ".join(fmt.humanize(c) for c in pre["columns_excluded"]) + ".")
    if pre["duplicates_removed"]:
        out.append(f"{pre['duplicates_removed']:,} exact duplicate records were removed before analysis.")
    if any(f["kind"] in ("correlation", "association", "group_difference") for f in findings):
        out.append("All relationships are associations in observational data; they do not establish cause and effect.")
    if ctx["rows"] < 100:
        out.append(f"The dataset is small ({ctx['rows']} rows), so estimates carry wide uncertainty.")
    out.append(f"Significance was judged after Benjamini–Hochberg correction across all {ctx['n_tests']} tests "
               f"run (α = {ctx['alpha']}), which limits false discoveries from testing many pairs.")
    return out


def template_story(ctx: dict, findings: list[dict]) -> dict:
    src = ctx["source_name"]
    if not findings:
        return {
            "headline": f"No statistically robust patterns found in {src}",
            "standfirst": (f"An automated analysis of {ctx['rows']:,} records ran {ctx['n_tests']} statistical tests; "
                           f"none survived correction for multiple comparisons."),
            "lede": ("That is itself a finding: apparent differences in this dataset are within the range "
                     "that chance alone would produce."),
            "sections": [], "caveats": _caveats(ctx, findings), "engine": "template",
        }
    top = findings[0]
    sections = [{"finding_id": f["id"], "heading": f["title"], "body": finding_text(f, ctx)} for f in findings]
    n_sig = ctx["n_significant"]
    return {
        "headline": top["title"],
        "standfirst": (f"An automated statistical analysis of {ctx['rows']:,} records from {src} ran "
                       f"{ctx['n_tests']} tests and found {n_sig} statistically significant "
                       f"pattern{'s' if n_sig != 1 else ''}. The {len(findings)} most newsworthy are reported below."),
        "lede": sections[0]["body"].split(". ")[0].rstrip(".") + ".",
        "sections": sections,
        "caveats": _caveats(ctx, findings),
        "engine": "template",
    }


# ---------------------------------------------------------------------------- fact checking
_NUM_RE = re.compile(r"(?<![\w.])[-+−]?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|%))?", re.I)


def _parse_token(tok: str) -> tuple[float, float] | None:
    t = tok.replace("−", "-").replace(",", "").strip().lower()
    mult = 1.0
    if t.endswith("billion"):
        mult, t = 1e9, t[:-7].strip()
    elif t.endswith("million"):
        mult, t = 1e6, t[:-7].strip()
    t = t.rstrip("%").strip()
    try:
        v = float(t)
    except ValueError:
        return None
    decimals = len(t.split(".")[1]) if "." in t else 0
    return v * mult, 0.5 * 10 ** (-decimals) * mult


def allowed_numbers(ctx: dict, findings: list[dict]) -> list[float]:
    vals: list[float] = [ctx["rows"], ctx["n_tests"], ctx["n_significant"], ctx["alpha"], len(findings),
                         0.001, 0.01, 0.05, 10, 90, 95, 100]
    blobs = [json.dumps(ctx.get("columns", []))]
    for f in findings:
        for fact in f["facts"]:
            if isinstance(fact["value"], (int, float)):
                vals.append(float(fact["value"]))
            blobs += [fact["label"], fact["display"]]
        s = f["stat"]
        for k in ("statistic", "p", "q", "effect", "n"):
            if isinstance(s.get(k), (int, float)):
                vals.append(float(s[k]))
        blobs.append(finding_text(f, ctx))
    for blob in blobs:
        for tok in _NUM_RE.findall(blob):
            parsed = _parse_token(tok)
            if parsed:
                vals.append(parsed[0])
    vals += [abs(v) for v in vals]
    return vals


def verify_text(text: str, allowed: list[float]) -> list[str]:
    """Return the number tokens in *text* that match no verified value."""
    bad = []
    for tok in _NUM_RE.findall(text):
        parsed = _parse_token(tok)
        if not parsed:
            continue
        v, half_unit = parsed
        if abs(v) <= 12 and float(v).is_integer():
            continue  # small counts ("three groups", "top 10") are structural, not claims
        tol = lambda ref: max(0.015 * abs(ref), half_unit)
        if not any(abs(v - a) <= tol(a) for a in allowed):
            bad.append(tok.strip())
    return bad


# ---------------------------------------------------------------------------- LLM engine
SYSTEM_PROMPT = """You are a data journalist at a serious newsroom. You turn statistically validated findings into a clear, engaging, accurate news story.

Rules:
- Use ONLY the numbers given in the findings (facts, statistics and sample sizes). Never invent, extrapolate or round to new figures beyond what is shown. You may copy a number's displayed form.
- Do not claim causation. Describe associations as associations.
- Mention statistical evidence in plain language (e.g. "statistically significant"), and keep test names brief.
- Write for a general audience: short paragraphs, concrete wording, no hype.

Output format (exactly these markers, nothing before HEADLINE):
HEADLINE: <one line, under 14 words>
STANDFIRST: <one or two sentences summarising the story>
LEDE: <one compelling opening sentence>
### <finding_id, e.g. F1> | <section heading>
<one paragraph, 2-4 sentences>
(repeat the ### block for every finding, in the given order)"""


def _llm_payload(ctx: dict, findings: list[dict]) -> str:
    items = []
    for i, f in enumerate(findings, 1):
        items.append({
            "finding_id": f"F{i}", "kind": f["kind"], "working_title": f["title"],
            "facts": [{"label": x["label"], "value": x["display"]} for x in f["facts"]],
            "statistics": {k: f["stat"].get(k) for k in ("test", "p", "q", "effect", "effect_name", "magnitude", "n")},
            "reference_text": finding_text(f, ctx),
        })
    return json.dumps({
        "dataset": {"name": ctx["source_name"], "rows": ctx["rows"], "tests_run": ctx["n_tests"],
                    "significant_findings": ctx["n_significant"], "description": ctx.get("description", "")},
        "findings": items,
    }, indent=1, default=str)


def _parse_llm(text: str, findings: list[dict]) -> dict:
    def grab(label: str) -> str:
        m = re.search(rf"^{label}:\s*(.+)$", text, re.M)
        return m.group(1).strip() if m else ""

    sections = {}
    for m in re.finditer(r"^###\s*(.+?)\s*\|\s*(.+?)\s*$\n(.*?)(?=^###|\Z)", text, re.M | re.S):
        sections[m.group(1).strip()] = {"heading": m.group(2).strip(), "body": " ".join(m.group(3).split())}
    return {"headline": grab("HEADLINE"), "standfirst": grab("STANDFIRST"), "lede": grab("LEDE"),
            "sections": sections}


def ai_story(ctx: dict, findings: list[dict], on_delta: Callable[[str], None], log) -> dict:
    """Generate the story with Claude, streaming deltas, then fact-check against verified numbers."""
    base = template_story(ctx, findings)
    if not findings:
        return base
    import anthropic

    client = anthropic.Anthropic()
    chunks: list[str] = []
    with client.beta.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
        messages=[{"role": "user", "content": "Write the story for these validated findings:\n\n"
                                               + _llm_payload(ctx, findings)}],
    ) as stream:
        for delta in stream.text_stream:
            chunks.append(delta)
            on_delta(delta)
        final = stream.get_final_message()
    if final.stop_reason == "refusal":
        log("AI narrative was declined by the model; falling back to statistical templates", "warning")
        return {**base, "verification": {"fallback": "refusal"}}

    parsed = _parse_llm("".join(chunks), findings)
    allowed = allowed_numbers(ctx, findings)
    report: list[dict] = []

    def checked(field: str, text: str, fallback: str) -> str:
        if not text:
            report.append({"part": field, "status": "missing", "action": "template used"})
            return fallback
        bad = verify_text(text, allowed)
        if bad:
            report.append({"part": field, "status": "unverified", "numbers": bad, "action": "template used"})
            return fallback
        report.append({"part": field, "status": "verified"})
        return text

    story = {
        "headline": checked("headline", parsed["headline"], base["headline"]),
        "standfirst": checked("standfirst", parsed["standfirst"], base["standfirst"]),
        "lede": checked("lede", parsed["lede"], base["lede"]),
        "sections": [], "caveats": base["caveats"], "engine": "ai", "model": final.model,
    }
    for i, (f, fallback) in enumerate(zip(findings, base["sections"]), 1):
        sec = parsed["sections"].get(f"F{i}")
        if not sec:
            report.append({"part": f["id"], "status": "missing", "action": "template used"})
            story["sections"].append(fallback)
            continue
        body = checked(f["id"], sec["body"], fallback["body"])
        heading = sec["heading"] if not verify_text(sec["heading"], allowed) else fallback["heading"]
        story["sections"].append({"finding_id": f["id"], "heading": heading, "body": body})
    n_ok = sum(r["status"] == "verified" for r in report)
    story["verification"] = {"checked": len(report), "verified": n_ok, "details": report}
    log(f"Fact-check: {n_ok}/{len(report)} AI-written parts verified against the statistics")
    return story


def generate(ctx: dict, findings: list[dict], mode: str, on_delta, log) -> dict:
    if mode == "ai":
        if not llm_available():
            log("AI narrative requested but no ANTHROPIC_API_KEY is configured — using statistical templates", "warning")
        else:
            try:
                return ai_story(ctx, findings, on_delta, log)
            except Exception as exc:  # network / auth / rate-limit — never lose the report
                log(f"AI narrative failed ({type(exc).__name__}: {exc}); using statistical templates", "warning")
    return template_story(ctx, findings)
