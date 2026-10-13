import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle, ArrowLeft, FastForward, FileText, Newspaper, Table2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Console from "../components/Console";
import DataPreview from "../components/DataPreview";
import FindingCard from "../components/FindingCard";
import PipelineRail from "../components/PipelineRail";
import PlotlyChart from "../components/PlotlyChart";
import ReportPanel from "../components/ReportPanel";
import StoryPanel from "../components/StoryPanel";
import { useRunStream } from "../hooks/useRunStream";
import { KIND_META, fmtNum, fmtP } from "../lib/format";

const TABS = [
  { id: "newsroom", label: "Newsroom", icon: Newspaper },
  { id: "report", label: "Report", icon: FileText },
  { id: "data", label: "Data & statistics", icon: Table2 },
];

function Elapsed({ start, end, running }) {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => {
    if (!running) return undefined;
    const t = setInterval(() => setNow(Date.now() / 1000), 100);
    return () => clearInterval(t);
  }, [running]);
  if (!start) return null;
  const s = Math.max(0, (end ?? now) - start);
  return <span className="font-mono tabular">{s.toFixed(1)}s</span>;
}

function StatusPill({ status }) {
  const map = {
    connecting: ["Connecting", "bg-dim"],
    queued: ["Queued", "bg-amber"],
    running: ["Live", "bg-accent"],
    done: ["Complete", "bg-teal"],
    error: ["Failed", "bg-accent"],
  };
  const [label, color] = map[status] ?? map.connecting;
  return (
    <span className="flex items-center gap-2 rounded-full border border-line bg-panel px-3 py-1 font-mono text-[11px] uppercase tracking-wider">
      <span className="relative flex h-2 w-2">
        {status === "running" && <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${color} opacity-70`} />}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${color}`} />
      </span>
      {label}
    </span>
  );
}

function PublishedStamp() {
  return (
    <motion.div
      initial={{ scale: 2.4, opacity: 0, rotate: -24 }}
      animate={{ scale: 1, opacity: 1, rotate: -8 }}
      transition={{ type: "spring", stiffness: 260, damping: 14 }}
      className="pointer-events-none select-none rounded-lg border-[3px] border-teal px-3 py-1 font-mono text-[15px] font-bold tracking-[0.25em] text-teal"
    >
      PUBLISHED
    </motion.div>
  );
}

function TestsTable({ tests }) {
  const [onlySig, setOnlySig] = useState(true);
  const rows = useMemo(
    () => [...tests].filter((t) => !onlySig || t.significant).sort((a, b) => (a.q ?? 1) - (b.q ?? 1)),
    [tests, onlySig]
  );
  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <span className="kicker">All statistical tests ({tests.length})</span>
        <label className="flex cursor-pointer items-center gap-2 text-[12px] text-muted">
          <input type="checkbox" checked={onlySig} onChange={(e) => setOnlySig(e.target.checked)} className="accent-[#ff5a36]" />
          Significant only
        </label>
      </div>
      <div className="max-h-[460px] overflow-auto">
        <table className="w-full text-left text-[12.5px]">
          <thead className="sticky top-0 bg-panel-2 font-mono text-[10.5px] uppercase tracking-wider text-muted">
            <tr>
              {["Test", "Columns", "Effect", "p", "q (FDR)", ""].map((h) => (
                <th key={h} className="whitespace-nowrap px-4 py-2 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id} className="border-t border-line/60">
                <td className="whitespace-nowrap px-4 py-2" style={{ color: KIND_META[t.kind]?.color }}>
                  {t.test}
                </td>
                <td className="px-4 py-2 text-text/85">{t.columns.join(" × ")}</td>
                <td className="whitespace-nowrap px-4 py-2 font-mono">
                  {t.effect_name} {t.effect != null ? t.effect.toFixed(3) : "—"} <span className="text-dim">({t.magnitude})</span>
                </td>
                <td className="px-4 py-2 font-mono">{fmtP(t.p)}</td>
                <td className="px-4 py-2 font-mono">{fmtP(t.q)}</td>
                <td className="px-4 py-2">{t.significant && <span className="rounded bg-teal/15 px-1.5 py-0.5 font-mono text-[10px] text-teal">SIG</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DataTab({ result }) {
  if (!result) return <p className="kicker shimmer">Waiting for the analysis to finish…</p>;
  const pre = result.preprocess;
  const an = result.anomalies;
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="lg:col-span-2">
        <DataPreview preview={result.preview} schema={result.ingest.schema} />
      </div>
      <div className="panel p-5">
        <div className="kicker mb-3">Preprocessing audit log</div>
        <ul className="space-y-2 text-[13px]">
          {pre.log.length === 0 && <li className="text-muted">No changes were needed — the data was already clean.</li>}
          {pre.log.map((e, i) => (
            <li key={i} className="flex gap-2">
              <span className="font-mono text-[11px] text-accent">{e.action}</span>
              <span className="text-text/80">
                {e.column ?? (Array.isArray(e.columns) ? e.columns.join(", ") : e.columns ? Object.keys(e.columns).join(", ") : "")}
                {e.count ? ` · ${e.count.toLocaleString()}` : ""}
                {e.reason ? <span className="text-muted"> — {e.reason}</span> : null}
              </span>
            </li>
          ))}
        </ul>
        {result.ingest.issues.length > 0 && (
          <>
            <div className="kicker mb-2 mt-5">Validation</div>
            <ul className="space-y-1.5 text-[13px]">
              {result.ingest.issues.map((i) => (
                <li key={i.message} className={`flex gap-2 ${i.level === "info" ? "text-muted" : "text-amber"}`}>
                  <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                  {i.message}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
      <div className="panel p-5">
        <div className="kicker mb-3">Anomalies (robust z-score &gt; 3.5)</div>
        <div className="max-h-[300px] space-y-1.5 overflow-auto font-mono text-[12px]">
          {an.points.length === 0 && <p className="text-muted">No extreme single values.</p>}
          {an.points.map((p, i) => (
            <div key={i} className="flex justify-between gap-3 border-b border-line/50 pb-1.5">
              <span className="truncate text-text/85">{p.label}</span>
              <span className="whitespace-nowrap text-muted">
                {p.column} = <span className="text-text">{fmtNum(p.value)}</span> <span className="text-accent">z {p.robust_z}</span>
              </span>
            </div>
          ))}
        </div>
        {an.multivariate.length > 0 && (
          <p className="mt-3 text-[12px] text-muted">
            Isolation Forest flagged {(an.multivariate_share * 100).toFixed(1)}% of records as multivariate outliers; top: {an.multivariate[0].label}.
          </p>
        )}
      </div>
      {result.overview_charts?.[0] && (
        <div className="panel p-4 lg:col-span-2">
          <div className="kicker mb-1 px-1">Correlation matrix</div>
          <PlotlyChart figure={result.overview_charts[0].figure} height={420} />
        </div>
      )}
      <div className="lg:col-span-2">
        <TestsTable tests={result.stats.tests} />
      </div>
    </div>
  );
}

export default function RunView() {
  const { id } = useParams();
  const s = useRunStream(id);
  const [tab, setTab] = useState("newsroom");
  const sections = useMemo(() => Object.fromEntries((s.story?.sections ?? []).map((x) => [x.finding_id, x.body])), [s.story]);
  const schema = s.stages.ingest?.summary?.schema;
  const running = s.status === "running" || s.status === "queued" || s.status === "connecting";
  const source = s.result?.source?.name ?? s.run?.source_name;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <Link to="/" className="grid h-9 w-9 place-items-center rounded-xl border border-line text-muted transition-colors hover:text-text">
          <ArrowLeft size={16} />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="kicker">Run {id.slice(0, 8)}</div>
          <h1 className="truncate font-serif text-[24px] font-semibold tracking-tight">{source ?? "Loading…"}</h1>
        </div>
        <div className="flex items-center gap-3 text-[13px] text-muted">
          {running && (
            <button onClick={s.skipAnimation} className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[12px] hover:text-text" title="Show all events immediately">
              <FastForward size={14} /> Skip
            </button>
          )}
          <Elapsed start={s.startedAt} end={s.finishedAt} running={running} />
          <StatusPill status={s.status} />
          <AnimatePresence>{s.status === "done" && <PublishedStamp />}</AnimatePresence>
        </div>
      </div>

      <PipelineRail stages={s.stages} />

      <AnimatePresence>
        {s.status === "error" && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex items-start gap-3 rounded-2xl border border-accent/40 bg-accent/10 p-4 text-[14px]">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-accent" />
            <div>
              <div className="font-semibold">The pipeline stopped</div>
              <div className="text-text/80">{s.error}</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex gap-1 border-b border-line">
        {TABS.map(({ id: t, label, icon: Icon }) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`relative flex items-center gap-2 px-4 py-2.5 text-[13.5px] font-medium ${tab === t ? "text-text" : "text-muted hover:text-text"}`}
          >
            <Icon size={15} />
            {label}
            {t === "report" && s.status === "done" && <span className="h-1.5 w-1.5 rounded-full bg-teal" />}
            {tab === t && <motion.span layoutId="run-tab" className="absolute inset-x-2 -bottom-px h-[2px] rounded bg-accent" />}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
          {tab === "newsroom" && (
            <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_400px]">
              <div className="space-y-5">
                <AnimatePresence>
                  {s.status === "done" && (
                    <motion.button
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      onClick={() => setTab("report")}
                      className="flex w-full items-center justify-between rounded-2xl border border-teal/30 bg-teal/10 px-5 py-3.5 text-left"
                    >
                      <span className="text-[14px]">
                        <b className="text-teal">Report published.</b> <span className="text-text/80">The full HTML news report is ready to read and download.</span>
                      </span>
                      <span className="font-mono text-[12px] text-teal">View →</span>
                    </motion.button>
                  )}
                </AnimatePresence>
                <StoryPanel story={s.story} streaming={s.narrativeText} stage={s.stages.narrative?.status} />
                {s.findings.length === 0 && running && (
                  <div className="panel grid h-[240px] place-items-center p-6 text-center">
                    <div>
                      <div className="kicker shimmer">Searching the data for stories</div>
                      <p className="mt-2 max-w-sm text-[13px] text-dim">Findings appear here the moment they pass statistical testing.</p>
                    </div>
                  </div>
                )}
                {s.findings.length === 0 && s.status === "done" && (
                  <div className="panel p-6 text-[14px] text-muted">No finding survived correction for multiple comparisons — the report explains why that is itself a result.</div>
                )}
                <motion.div layout className="space-y-5">
                  {s.findings.map((f, i) => (
                    <FindingCard key={f.id} finding={f} index={i} body={sections[f.id]} />
                  ))}
                </motion.div>
              </div>
              <div className="space-y-5 lg:sticky lg:top-28">
                <Console logs={s.logs} status={s.status} />
                <DataPreview preview={s.preview} schema={schema} />
              </div>
            </div>
          )}
          {tab === "report" &&
            (s.status === "done" ? (
              <ReportPanel runId={id} />
            ) : (
              <div className="panel grid h-[300px] place-items-center">
                <span className="kicker shimmer">{s.status === "error" ? "No report — the run failed" : "The report is being written…"}</span>
              </div>
            ))}
          {tab === "data" && <DataTab result={s.result} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
