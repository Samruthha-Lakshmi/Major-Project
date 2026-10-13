import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, Lightbulb } from "lucide-react";
import { useState } from "react";
import { KIND_META, fmtNum, fmtP } from "../lib/format";
import PlotlyChart from "./PlotlyChart";

function ScoreBar({ score }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-line-2">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-amber to-accent"
          initial={{ width: 0 }}
          animate={{ width: `${Math.round(score * 100)}%` }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
        />
      </div>
      <span className="font-mono text-[10.5px] text-muted tabular">{score.toFixed(2)}</span>
    </div>
  );
}

export default function FindingCard({ finding: f, index, body }) {
  const [open, setOpen] = useState(false);
  const meta = KIND_META[f.kind] ?? { label: f.kind, color: "#8b919b" };
  const s = f.stat || {};

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 24, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 160, damping: 22 }}
      className="panel overflow-hidden"
    >
      <div className="p-5">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[11px] text-dim">{String(index + 1).padStart(2, "0")}</span>
          <span
            className="rounded-full px-2 py-0.5 font-mono text-[10.5px] font-semibold uppercase tracking-wider"
            style={{ color: meta.color, background: `${meta.color}1a` }}
          >
            {meta.label}
          </span>
          {s.magnitude && s.magnitude !== "unknown" && (
            <span className="rounded-full border border-line px-2 py-0.5 text-[11px] text-muted">{s.magnitude} effect</span>
          )}
          <div className="ml-auto">
            <ScoreBar score={f.score} />
          </div>
        </div>
        <h3 className="font-serif text-[22px] font-semibold leading-snug tracking-tight">{f.title}</h3>
        {body && (
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 text-[14.5px] leading-relaxed text-text/80">
            {body}
          </motion.p>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          {f.facts.slice(0, 4).map((fact) => (
            <div key={fact.label} className="rounded-xl border border-line bg-panel-2/70 px-3 py-2">
              <div className="font-serif text-[18px] font-semibold text-text tabular">{fact.display}</div>
              <div className="max-w-[220px] truncate text-[11px] text-muted" title={fact.label}>
                {fact.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      <AnimatePresence mode="wait">
        {f.chart ? (
          <motion.div
            key="chart"
            initial={{ opacity: 0, clipPath: "inset(0 100% 0 0)" }}
            animate={{ opacity: 1, clipPath: "inset(0 0% 0 0)" }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="border-t border-line bg-ink/40 px-2 pt-2"
          >
            <PlotlyChart figure={f.chart.figure} height={300} />
            <div className="flex items-start gap-2 px-3 pb-3 text-[12px] text-muted">
              <Lightbulb size={14} className="mt-0.5 shrink-0 text-amber" />
              <span>{f.chart.reason}</span>
            </div>
          </motion.div>
        ) : (
          <motion.div key="wait" exit={{ opacity: 0 }} className="border-t border-line px-5 py-6">
            <span className="kicker shimmer">Choosing the right chart…</span>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between border-t border-line px-5 py-3 text-left text-[12px] text-muted transition-colors hover:bg-white/[0.02] hover:text-text"
      >
        <span className="font-mono">
          {s.test}
          {s.p !== null && s.p !== undefined && ` · p ${fmtP(s.p)}`}
          {s.q !== null && s.q !== undefined && ` · q ${fmtP(s.q)}`}
        </span>
        <motion.span animate={{ rotate: open ? 180 : 0 }}>
          <ChevronDown size={16} />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 px-5 pb-4 font-mono text-[12px] sm:grid-cols-3">
              {[
                ["Statistic", s.statistic != null ? fmtNum(s.statistic, 4) : null],
                ["p-value", s.p != null ? fmtP(s.p) : null],
                ["FDR q-value", s.q != null ? fmtP(s.q) : null],
                ["Effect", s.effect != null ? `${s.effect_name} = ${s.effect.toFixed(3)}` : null],
                ["Sample", s.n ? `n = ${s.n.toLocaleString()}` : null],
                ["Robustness", f.details?.alt_test ? `${f.details.alt_test} p ${fmtP(f.details.alt_p)}` : null],
                ...f.facts.slice(4).map((x) => [x.label, x.display]),
              ]
                .filter(([, v]) => v)
                .map(([k, v]) => (
                  <div key={k} className="min-w-0">
                    <dt className="truncate text-dim" title={k}>
                      {k}
                    </dt>
                    <dd className="text-text">{v}</dd>
                  </div>
                ))}
            </dl>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}
