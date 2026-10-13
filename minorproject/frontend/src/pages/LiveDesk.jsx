import { AnimatePresence, motion } from "motion/react";
import { ArrowUpRight, CircleStop, Loader2, Minus, Plus, Radio, Satellite } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useFeed } from "../hooks/useFeed";
import { api } from "../lib/api";
import { timeAgo } from "../lib/format";

const INTERVALS = [
  { v: 60, l: "1 min" },
  { v: 300, l: "5 min" },
  { v: 900, l: "15 min" },
  { v: 3600, l: "1 hour" },
];

function Countdown({ nextAt, interval, status }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, []);
  const r = 22;
  const c = 2 * Math.PI * r;
  const left = nextAt ? Math.max(0, (new Date(nextAt).getTime() - now) / 1000) : 0;
  const frac = status === "waiting" && nextAt ? left / interval : 1;
  return (
    <div className="relative grid h-14 w-14 place-items-center">
      <svg viewBox="0 0 52 52" className="absolute inset-0 -rotate-90">
        <circle cx="26" cy="26" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3" />
        <motion.circle
          cx="26"
          cy="26"
          r={r}
          fill="none"
          stroke={status === "running" ? "#ff5a36" : "#1fb5a8"}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={c}
          animate={{ strokeDashoffset: c * (1 - frac) }}
          transition={{ duration: 0.25, ease: "linear" }}
        />
      </svg>
      {status === "running" || status === "starting" ? (
        <Loader2 size={16} className="animate-spin text-accent" />
      ) : (
        <span className="font-mono text-[11px] tabular">{left >= 60 ? `${Math.ceil(left / 60)}m` : `${Math.ceil(left)}s`}</span>
      )}
    </div>
  );
}

function WatcherCard({ w, onStop }) {
  const d = w.last_diff;
  return (
    <motion.div layout initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.94 }} className="panel p-5">
      <div className="flex items-start gap-4">
        <Countdown nextAt={w.next_at} interval={w.interval_s} status={w.status} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[15px] font-semibold">{w.source_name}</span>
            <span className="rounded-full bg-panel-2 px-2 py-0.5 font-mono text-[10.5px] text-muted">
              every {INTERVALS.find((i) => i.v === w.interval_s)?.l ?? `${w.interval_s}s`}
            </span>
            {Object.entries(w.params || {}).map(([k, v]) => (
              <span key={k} className="font-mono text-[10.5px] text-dim">
                {k}={String(v)}
              </span>
            ))}
          </div>
          <div className="mt-0.5 font-mono text-[11px] text-dim">
            {w.runs} edition{w.runs === 1 ? "" : "s"} · {w.status}
          </div>
        </div>
        <button onClick={() => onStop(w.id)} className="rounded-lg p-1.5 text-dim transition-colors hover:bg-accent/10 hover:text-accent" title="Stop watching">
          <CircleStop size={18} />
        </button>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={w.last_headline ?? "none"}
          initial={{ opacity: 0, y: 10, filter: "blur(4px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          exit={{ opacity: 0, y: -10 }}
          className="mt-4"
        >
          {w.last_headline ? (
            <h3 className="font-serif text-[20px] font-semibold leading-snug">{w.last_headline}</h3>
          ) : w.last_error ? (
            <p className="text-[13px] text-accent">{w.last_error}</p>
          ) : (
            <p className="kicker shimmer">Fetching the first edition…</p>
          )}
        </motion.div>
      </AnimatePresence>

      {d && !d.first && (
        <div className="mt-3 flex flex-wrap gap-1.5 text-[11.5px]">
          <span className="rounded-md bg-panel-2 px-2 py-0.5 font-mono text-muted">
            rows {d.rows_before?.toLocaleString()} → {d.rows_after?.toLocaleString()}
          </span>
          {d.headline_changed && <span className="rounded-md bg-accent/15 px-2 py-0.5 font-mono text-accent">new lead story</span>}
          {d.new_findings?.map((t) => (
            <span key={t} className="flex items-center gap-1 rounded-md bg-teal/10 px-2 py-0.5 text-teal">
              <Plus size={11} /> {t}
            </span>
          ))}
          {d.dropped_findings?.map((t) => (
            <span key={t} className="flex items-center gap-1 rounded-md bg-white/5 px-2 py-0.5 text-dim line-through">
              <Minus size={11} /> {t}
            </span>
          ))}
          {!d.headline_changed && !d.new_findings?.length && !d.dropped_findings?.length && (
            <span className="rounded-md bg-panel-2 px-2 py-0.5 text-muted">story unchanged</span>
          )}
        </div>
      )}

      {w.last_run_id && (
        <Link to={`/runs/${w.last_run_id}`} className="mt-4 inline-flex items-center gap-1 text-[12.5px] text-muted hover:text-text">
          Open latest edition <ArrowUpRight size={13} />
        </Link>
      )}
    </motion.div>
  );
}

const WIRE_TEXT = {
  run_started: (e) => ["started", e.run.source_name],
  run_finished: (e) => [e.run.status === "done" ? "published" : "failed", e.run.headline ?? e.run.error ?? e.run.source_name],
  watcher: (e) => [e.watcher.status === "running" ? "refreshing" : "scheduled", e.watcher.source_name],
  watcher_removed: () => ["stopped", "a watcher"],
  run_deleted: () => ["deleted", "a report"],
};

export default function LiveDesk() {
  const { watchers, setWatchers, wire, connected } = useFeed();
  const [sources, setSources] = useState([]);
  const [form, setForm] = useState({ source: "usgs", params: {}, interval_s: 300, narrative_mode: "template" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.sources().then((s) => {
      setSources(s);
      const first = s[0];
      setForm((f) => ({ ...f, params: Object.fromEntries(first.params.map((p) => [p.name, p.default])) }));
    });
  }, []);

  const src = sources.find((s) => s.id === form.source);
  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const w = await api.createWatcher(form);
      setWatchers((x) => ({ ...x, [w.id]: w }));
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  };
  const stop = async (id) => {
    await api.deleteWatcher(id).catch(() => {});
    setWatchers((x) => {
      const n = { ...x };
      delete n[id];
      return n;
    });
  };
  const list = Object.values(watchers);

  return (
    <div className="space-y-8">
      <div>
        <div className="kicker flex items-center gap-2">
          <Radio size={13} className="text-accent" /> Live Desk
        </div>
        <h1 className="mt-2 font-serif text-[40px] font-extrabold leading-tight tracking-tight sm:text-[52px]">Stories that update themselves.</h1>
        <p className="mt-3 max-w-2xl text-[16px] text-muted">
          Point the pipeline at a real-time public feed and it re-runs on a schedule — fetching fresh data, re-testing every
          finding and publishing a new edition, with a diff of what changed since the last one.
        </p>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[360px_minmax(0,1fr)_320px]">
        <div className="panel space-y-4 p-5">
          <div className="kicker">New watch</div>
          <div className="space-y-2">
            {sources.map((s) => (
              <button
                key={s.id}
                onClick={() => setForm((f) => ({ ...f, source: s.id, params: Object.fromEntries(s.params.map((p) => [p.name, p.default])) }))}
                className={`relative w-full rounded-xl border px-3 py-2.5 text-left text-[13.5px] transition-colors ${form.source === s.id ? "border-accent/50 bg-accent/[0.06]" : "border-line hover:border-line-2"}`}
              >
                <div className="font-semibold">{s.name}</div>
                <div className="text-[12px] text-muted">{s.description}</div>
              </button>
            ))}
          </div>
          {src?.params.map((p) => (
            <label key={p.name} className="block text-[12px] text-muted">
              {p.label}
              <select
                value={form.params[p.name] ?? p.default}
                onChange={(e) => setForm((f) => ({ ...f, params: { ...f.params, [p.name]: e.target.value } }))}
                className="mt-1 w-full rounded-lg border border-line-2 bg-panel-2 px-2 py-1.5 text-[13px] text-text outline-none focus:border-accent"
              >
                {p.options.map((o) => (
                  <option key={o} value={o}>
                    {p.labels?.[o] ?? o.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <div>
            <div className="mb-1.5 text-[12px] text-muted">Refresh every</div>
            <div className="grid grid-cols-4 gap-1 rounded-xl border border-line bg-ink/60 p-1">
              {INTERVALS.map((i) => (
                <button
                  key={i.v}
                  onClick={() => setForm((f) => ({ ...f, interval_s: i.v }))}
                  className={`relative rounded-lg py-1.5 text-[12px] ${form.interval_s === i.v ? "text-text" : "text-muted"}`}
                >
                  {form.interval_s === i.v && <motion.span layoutId="interval" className="absolute inset-0 rounded-lg bg-panel-2 ring-1 ring-line-2" />}
                  <span className="relative">{i.l}</span>
                </button>
              ))}
            </div>
          </div>
          {error && <p className="text-[12.5px] text-accent">{error}</p>}
          <motion.button
            whileTap={{ scale: 0.98 }}
            disabled={busy || !connected}
            onClick={start}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent py-3 text-[14px] font-semibold text-ink disabled:opacity-50"
          >
            {busy ? <Loader2 size={16} className="animate-spin" /> : <Satellite size={16} />}
            Start watching
          </motion.button>
        </div>

        <div className="space-y-4">
          <AnimatePresence mode="popLayout">
            {list.map((w) => (
              <WatcherCard key={w.id} w={w} onStop={stop} />
            ))}
          </AnimatePresence>
          {!list.length && (
            <div className="panel grid h-[320px] place-items-center p-8 text-center">
              <div>
                <motion.div animate={{ scale: [1, 1.12, 1] }} transition={{ duration: 2.4, repeat: Infinity }} className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full border border-line-2">
                  <Radio size={22} className="text-muted" />
                </motion.div>
                <div className="font-serif text-[20px] font-semibold">No feeds on the wire yet</div>
                <p className="mt-1 text-[13px] text-muted">Start a watch to publish a fresh edition on a schedule.</p>
              </div>
            </div>
          )}
        </div>

        <div className="panel flex max-h-[640px] flex-col overflow-hidden">
          <div className="flex items-center gap-2 border-b border-line px-4 py-3">
            <span className={`h-2 w-2 rounded-full ${connected ? "animate-pulse bg-teal" : "bg-dim"}`} />
            <span className="kicker">The wire</span>
          </div>
          <div className="flex-1 space-y-2 overflow-y-auto p-3">
            <AnimatePresence initial={false}>
              {wire.map((e) => {
                const [verb, text] = (WIRE_TEXT[e.type] ?? (() => [e.type, ""]))(e);
                return (
                  <motion.div key={e.key} initial={{ opacity: 0, x: 20, height: 0 }} animate={{ opacity: 1, x: 0, height: "auto" }} className="rounded-lg border border-line bg-panel-2/60 px-3 py-2">
                    <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider">
                      <span className={verb === "published" ? "text-teal" : verb === "failed" ? "text-accent" : "text-amber"}>{verb}</span>
                      <span className="text-dim">{timeAgo(new Date(e.ts * 1000).toISOString())}</span>
                    </div>
                    <div className="mt-0.5 line-clamp-2 text-[12.5px] text-text/85">{text}</div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
            {!wire.length && <p className="p-2 text-[12.5px] text-dim">Events from every run appear here in real time.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
