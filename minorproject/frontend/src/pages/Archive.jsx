import { AnimatePresence, motion } from "motion/react";
import { Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useFeed } from "../hooks/useFeed";
import { api } from "../lib/api";
import { fmtMs, timeAgo } from "../lib/format";

const FILTERS = ["all", "live", "sample", "upload"];

export default function Archive() {
  const { runs, setRuns } = useFeed();
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const shown = useMemo(
    () =>
      runs.filter(
        (r) =>
          (filter === "all" || r.source_type === filter) &&
          (!q || `${r.headline} ${r.source_name}`.toLowerCase().includes(q.toLowerCase()))
      ),
    [runs, filter, q]
  );
  const remove = async (id) => {
    await api.deleteRun(id).catch(() => {});
    setRuns((rs) => rs.filter((r) => r.id !== id));
  };

  return (
    <div className="space-y-8">
      <div>
        <div className="kicker">Archive</div>
        <h1 className="mt-2 font-serif text-[40px] font-extrabold tracking-tight sm:text-[52px]">Every edition, on file.</h1>
        <p className="mt-2 text-[15px] text-muted">Each run is stored in SQLite with its statistics, findings, event log and published report.</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-full border border-line bg-panel/60 p-1">
          {FILTERS.map((f) => (
            <button key={f} onClick={() => setFilter(f)} className={`relative rounded-full px-4 py-1.5 text-[13px] capitalize ${filter === f ? "text-ink" : "text-muted hover:text-text"}`}>
              {filter === f && <motion.span layoutId="arch-filter" className="absolute inset-0 rounded-full bg-text" />}
              <span className="relative">{f}</span>
            </button>
          ))}
        </div>
        <label className="ml-auto flex items-center gap-2 rounded-full border border-line bg-panel/60 px-4 py-2">
          <Search size={14} className="text-muted" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search headlines…" className="w-56 bg-transparent text-[13px] outline-none placeholder:text-dim" />
        </label>
      </div>

      <div className="panel overflow-hidden">
        <div className="hidden grid-cols-[1fr_140px_110px_90px_90px_40px] gap-4 border-b border-line px-5 py-3 font-mono text-[10.5px] uppercase tracking-wider text-dim md:grid">
          <span>Headline</span>
          <span>Source</span>
          <span>Rows</span>
          <span>Time</span>
          <span>Status</span>
          <span />
        </div>
        <AnimatePresence initial={false}>
          {shown.map((r, i) => (
            <motion.div
              key={r.id}
              layout
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0, transition: { delay: Math.min(i * 0.03, 0.4) } }}
              exit={{ opacity: 0, x: -40, height: 0 }}
              className="group grid grid-cols-1 items-center gap-1 border-b border-line/60 px-5 py-4 md:grid-cols-[1fr_140px_110px_90px_90px_40px] md:gap-4"
            >
              <Link to={`/runs/${r.id}`} className="min-w-0">
                <div className="truncate font-serif text-[17px] font-semibold group-hover:text-white">{r.headline ?? r.error ?? "In progress…"}</div>
                <div className="truncate text-[12px] text-muted">
                  {r.source_name} · {timeAgo(r.created_at)}
                </div>
              </Link>
              <span className="font-mono text-[11.5px] capitalize text-muted">{r.source_type}</span>
              <span className="font-mono text-[11.5px] text-muted">{r.rows?.toLocaleString() ?? "—"}</span>
              <span className="font-mono text-[11.5px] text-muted">{fmtMs(r.duration_ms)}</span>
              <span className={`font-mono text-[11px] uppercase ${r.status === "done" ? "text-teal" : r.status === "error" ? "text-accent" : "text-amber"}`}>{r.status}</span>
              <button onClick={() => remove(r.id)} className="justify-self-start rounded-lg p-1.5 text-dim opacity-0 transition hover:bg-accent/10 hover:text-accent group-hover:opacity-100 md:justify-self-end" title="Delete">
                <Trash2 size={15} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
        {!shown.length && <p className="p-8 text-center text-[14px] text-muted">Nothing here yet — run the pipeline from the Studio.</p>}
      </div>
    </div>
  );
}
