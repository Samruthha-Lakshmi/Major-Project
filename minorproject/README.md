# The Data Desk — Automated Data Journalism Pipeline

**Automated Data Journalism Pipeline for Statistical Analysis and HTML News Report Generation**
Department of Artificial Intelligence and Data Science · Dhanalakshmi College of Engineering · 2025–2026
Guided by Dr K Dhinakaran · Presented by Yuvanesh R

> *Statistically grounded AI-generated journalism* — an end-to-end pipeline that turns a raw dataset (or a live public data feed) into a statistically validated, publication-ready HTML news report, streamed to the browser stage by stage in real time.

---

## What it does

1. **Ingestion & validation** — CSV / TSV / Excel / JSON / GeoJSON. Delimiter and encoding sniffing, currency/percent/thousands parsing, and semantic type inference for every column (numeric, datetime, categorical, boolean, text, identifier).
2. **Preprocessing** — removes empty rows/columns and exact duplicates, median-imputes numeric gaps under 30 %, labels missing categories `Unknown`, excludes columns over 60 % missing, and *flags* (never deletes) IQR outliers. Every action goes into an audit log printed in the report.
3. **Exploratory analysis** — per-column profiles (moments, quantiles, skew, histograms, entropy) and automatic selection of a time axis and resampling frequency.
4. **Statistical analysis** — every sensible column pair is tested:
   | Pair | Test | Effect size |
   |---|---|---|
   | numeric × numeric | Pearson r (+ Spearman ρ check) | r |
   | category × numeric, 2 groups | Welch t-test / Mann–Whitney U | Cohen's d |
   | category × numeric, 3+ groups | One-way ANOVA / Kruskal–Wallis | η² |
   | category × category | χ² independence | Cramér's V |
   | time × numeric | Kendall τ + OLS slope (statsmodels) | τ |

   The non-parametric variant is chosen when groups are small and non-normal (Shapiro–Wilk). **All p-values are corrected together with Benjamini–Hochberg FDR control**; a finding counts only if q < α *and* its effect size is non-negligible.
5. **Insight & anomaly detection** — findings ranked by newsworthiness (35 % statistical strength, 35 % effect size, 30 % story type). Tautologies are filtered (near-identical measures with |r| > 0.98; categories cut directly from a measure, e.g. Pass/Fail from a score). Anomalies via robust z-scores (median/MAD), a scikit-learn **Isolation Forest**, and rolling-median spike detection on the time series.
6. **Visualization recommendation** — one chart per finding chosen from the data's shape (trend → line + fitted trend, correlation → scatter + fit, group gap → ranked bars with 95 % CIs, association → row-% heatmap, spike → highlighted series, anomaly → box plot, concentration → Lorenz curve), each with a stated reason. Built in Plotly.
7. **Narrative generation** — two engines with one contract: *every number must come from a validated finding*.
   - **Statistical** (default): deterministic templates driven by the test results.
   - **Claude AI** (optional): Claude writes the story from the validated facts only, streamed live to the UI; then a **fact-checker** extracts every number it wrote and matches it to the verified facts at displayed precision. Any passage containing an untraceable number is replaced with the statistical version, and the swap is disclosed in the report.
8. **HTML report** — Jinja2-rendered, responsive, light/dark, print-friendly news article: headline, standfirst, key-numbers strip, lede, one section per finding with interactive chart and a collapsible statistical note, records-to-verify table, methodology, caveats, data-quality notes and a descriptive-statistics appendix. Download as HTML (CDN Plotly) or a fully **offline** single file.

### Real-time features
- **Live pipeline streaming** — a WebSocket carries every stage transition, log line, inferred schema, data preview, finding, chart and (in AI mode) every narrative token to the browser as it happens.
- **Live data feeds** (no API keys): USGS earthquakes (updated every minute), Open-Meteo hourly weather for seven cities, World Bank development indicators.
- **Live Desk** — schedule a feed to be re-analysed every 1 / 5 / 15 / 60 minutes; each new edition is diffed against the previous one (rows, lead story, findings gained/dropped).
- **Newsroom wire & ticker** — a global WebSocket pushes every run start/finish to all open tabs; headlines scroll in a breaking-news ticker.

### Interface
React + **Motion (motion.dev)** + Tailwind CSS, built with Vite: animated pipeline rail (spring-driven progress, pulsing active stage, self-drawing check marks), shared-layout tab and nav indicators, staggered finding cards with chart wipe-ins, live typing narrative, "PUBLISHED" stamp, countdown rings on the Live Desk, count-up statistics, page transitions, cursor-following glow, and full `prefers-reduced-motion` support.

---

## Quick start (Windows)

Requirements: Python 3.10+ and Node.js 20+.

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1   # once
powershell -ExecutionPolicy Bypass -File .\start.ps1   # opens http://localhost:5173
```

Or manually:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\make_samples.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --reload

# second terminal
cd frontend
npm.cmd install
npm.cmd run dev
```

**Single-process mode:** run `npm.cmd run build` in `frontend/` once; the FastAPI server then also serves the UI at http://localhost:8000.

**AI narrative (optional):** copy `backend/.env.example` to `backend/.env` and set `ANTHROPIC_API_KEY`. The "Claude AI" engine button activates automatically. Without a key everything works with the statistical engine.

### Command line (no server)

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\run_pipeline.py data\samples\student_performance.csv -o report.html
.\.venv\Scripts\python.exe scripts\run_pipeline.py --live usgs -o earthquakes.html
.\.venv\Scripts\python.exe scripts\run_pipeline.py my_data.xlsx --ai --alpha 0.01
```

### Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests
```

The suite checks type inference, loaders, preprocessing, that planted effects are detected and pure noise is not, trend detection, the fact-checker (accepts true numbers, rejects invented ones), and full end-to-end runs on every sample — including that the statistical narrative passes its own fact-check.

---

## Architecture

```
Browser (React · Motion · Plotly.js)
   │  REST  /api/*           WebSocket /ws/runs/{id}  (per-run event stream, with replay)
   │                         WebSocket /ws/feed        (newsroom-wide events)
FastAPI ─── run manager (asyncio, 3 concurrent runs) ─── Live Desk watchers (asyncio tasks)
   │
   └─ worker thread: pipeline/runner.py
        ingest → preprocess → eda → stats → insights → viz → narrative → report
        Pandas   Pandas/NumPy  SciPy  SciPy/Statsmodels  Scikit-learn  Plotly  Templates/Claude  Jinja2
   │
SQLite (backend/data/adj.sqlite): runs · results · event logs · rendered reports
```

```
minorproject/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, WebSockets, run manager, Live Desk watchers
│   │   ├── events.py          thread-safe pub/sub with replay buffers
│   │   ├── db.py              SQLite persistence
│   │   ├── pipeline/          ingest · preprocess · eda · stats · insights · viz · narrative · report · runner
│   │   ├── sources/live.py    USGS, Open-Meteo, World Bank fetchers
│   │   └── templates/report.html.j2
│   ├── scripts/               make_samples.py · run_pipeline.py (CLI)
│   ├── tests/                 pytest suite
│   └── data/samples/          seeded synthetic demo datasets
└── frontend/
    └── src/                   pages (Studio, RunView, LiveDesk, Archive, Method), components, hooks
```

### REST API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/runs` | start a run (`mode` = upload / sample / live, `narrative_mode`, `alpha`) |
| GET | `/api/runs`, `/api/runs/{id}` | list runs / full result |
| GET | `/api/runs/{id}/report.html` | report (`?offline=1`, `?download=1`) |
| GET | `/api/runs/{id}/result.json` | full analysis as JSON |
| DELETE | `/api/runs/{id}` | delete a run |
| GET/POST/DELETE | `/api/watchers` | Live Desk schedules |
| GET | `/api/health`, `/api/samples`, `/api/sources`, `/api/stats` | metadata |

Interactive docs: http://localhost:8000/docs

---

## Data notes

- The three bundled sample datasets are **synthetic** (generated by `scripts/make_samples.py` with a fixed seed) and labelled as such in the UI. They contain planted patterns, gaps, duplicates and a data-entry error so every stage has something to do. For real data, upload a file or use a live feed.
- Live feeds are fetched at run time from their public APIs; nothing is cached or invented. If a feed is unreachable the run fails with a clear message.

## Review-1 objectives → implementation

| Objective (Review 1 deck) | Where |
|---|---|
| Ingest, validate and preprocess datasets | `pipeline/ingest.py`, `pipeline/preprocess.py` |
| Descriptive and inferential statistics | `pipeline/eda.py`, `pipeline/stats.py` |
| Detect trends, relationships, anomalies | `pipeline/stats.py`, `pipeline/insights.py` |
| Extract statistical insights automatically | `pipeline/insights.py` (ranking, de-duplication) |
| Recommend suitable visualizations | `pipeline/viz.py` |
| Convert validated findings into narratives | `pipeline/narrative.py` (templates + Claude + fact-check) |
| Structured, responsive HTML reports | `pipeline/report.py`, `templates/report.html.j2` |
| Reduce manual effort; reproducible, auditable | one-click runs, audit log, SQLite archive, CLI |
| Future scope: real-time sources, fact verification | Live feeds, Live Desk, numeric fact-checker |

Deviation from the deck: the interface is React + FastAPI instead of Streamlit, to support live WebSocket streaming and the animated UI.

## Suggested references (to replace the deck's placeholders)

Please verify volume/page details against the publisher before final submission.

1. M. Carlson, "The Robotic Reporter: Automated journalism and the redefinition of labor, compositional forms, and journalistic authority," *Digital Journalism*, 3(3), 2015.
2. A. Graefe, *Guide to Automated Journalism*, Tow Center for Digital Journalism, Columbia University, 2016.
3. L. Leppänen, M. Munezero, M. Granroth-Wilding, H. Toivonen, "Data-Driven News Generation for Automated Journalism," *Proc. INLG*, 2017.
4. A. Gatt, E. Krahmer, "Survey of the State of the Art in Natural Language Generation: Core tasks, applications and evaluation," *JAIR*, 61, 2018.
5. S. Wiseman, S. Shieber, A. Rush, "Challenges in Data-to-Document Generation," *Proc. EMNLP*, 2017.
6. Z. Ji et al., "Survey of Hallucination in Natural Language Generation," *ACM Computing Surveys*, 55(12), 2023.
7. K. Wongsuphasawat et al., "Voyager: Exploratory Analysis via Faceted Browsing of Visualization Recommendations," *IEEE TVCG*, 22(1), 2016.
8. D. Moritz et al., "Formalizing Visualization Design Knowledge as Constraints: Actionable and Extensible Models in Draco," *IEEE TVCG*, 25(1), 2019.
9. B. Tang, S. Han, M. L. Yiu, R. Ding, D. Zhang, "Extracting Top-K Insights from Multi-dimensional Data," *Proc. ACM SIGMOD*, 2017.
10. Y. Benjamini, Y. Hochberg, "Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing," *J. Royal Statistical Society B*, 57(1), 1995.
11. F. T. Liu, K. M. Ting, Z.-H. Zhou, "Isolation Forest," *Proc. IEEE ICDM*, 2008.
