import { motion } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AnimatedNumber from "../components/AnimatedNumber";
import SourcePicker from "../components/SourcePicker";
import { useFeed } from "../hooks/useFeed";
import { api } from "../lib/api";
import { STAGES, fmtMs, timeAgo } from "../lib/format";

const words = ["From", "raw", "data", "to", "a", "published", "story."];

export default function Studio() {
  const { runs } = useFeed();
  const [stats, setStats] = useState(null);
  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
  }, [runs.length]);
  const recent = runs.filter((r) => r.status === "done").slice(0, 6);

  return (
    <div className="space-y-16">
      <section className="grid items-start gap-10 lg:grid-cols-[1.1fr_1fr]">
        <div className="pt-4 lg:pt-10">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mb-6 inline-flex items-center gap-2 rounded-full border border-line bg-panel/60 px-3 py-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <span className="kicker !text-[10.5px]">Statistically grounded AI-generated journalism</span>
          </motion.div>
          <h1 className="font-serif text-[46px] font-extrabold leading-[1.02] tracking-[-0.03em] sm:text-[64px] xl:text-[76px]">
            {words.map((w, i) => (
              <motion.span
                key={i}
                initial={{ opacity: 0, y: 30, rotateX: -40 }}
                animate={{ opacity: 1, y: 0, rotateX: 0 }}
                transition={{ delay: 0.08 * i, type: "spring", stiffness: 120, damping: 16 }}
                className={`mr-[0.22em] inline-block ${w === "published" ? "italic text-accent" : ""}`}
              >
                {w}
              </motion.span>
            ))}
          </h1>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }} className="mt-6 max-w-[560px] text-[17px] leading-relaxed text-muted">
            An eight-stage pipeline ingests a dataset, cleans it, runs a family of statistical tests with false-discovery
            control, detects anomalies, picks the right chart for every finding, writes fact-checked news copy and
            publishes a responsive HTML report — streamed to you live, stage by stage.
          </motion.p>

          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.85 }} className="mt-10 grid max-w-[560px] grid-cols-3 gap-px overflow-hidden rounded-2xl border border-line bg-line">
            {[
              ["Reports published", stats?.runs],
              ["Rows analysed", stats?.rows_analysed],
              ["Findings verified", stats?.findings],
            ].map(([label, v]) => (
              <div key={label} className="bg-ink/90 p-4">
                <div className="font-serif text-[30px] font-semibold tracking-tight">
                  <AnimatedNumber value={v ?? 0} />
                </div>
                <div className="text-[12px] text-muted">{label}</div>
              </div>
            ))}
          </motion.div>
          {stats?.avg_ms > 0 && (
            <p className="mt-3 font-mono text-[11.5px] text-dim">Average pipeline time: {fmtMs(Math.round(stats.avg_ms))}</p>
          )}
        </div>

        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, type: "spring", stiffness: 90, damping: 18 }}>
          <SourcePicker />
        </motion.div>
      </section>

      <section>
        <div className="mb-5 flex items-end justify-between">
          <div>
            <div className="kicker">The pipeline</div>
            <h2 className="mt-1 font-serif text-[28px] font-semibold tracking-tight">Eight stages, one click</h2>
          </div>
          <Link to="/method" className="flex items-center gap-1 text-[13px] text-muted hover:text-text">
            Methodology <ArrowUpRight size={14} />
          </Link>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STAGES.map((s, i) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ delay: (i % 4) * 0.07 }}
              whileHover={{ y: -4 }}
              className="panel group relative overflow-hidden p-5"
            >
              <div className="absolute right-4 top-3 font-serif text-[54px] font-extrabold leading-none text-white/[0.04] transition-colors group-hover:text-accent/15">
                {i + 1}
              </div>
              <div className="font-mono text-[10.5px] text-accent">{s.tech}</div>
              <div className="mt-2 text-[16px] font-semibold">{s.long}</div>
              <div className="mt-1 text-[13px] leading-relaxed text-muted">{s.desc}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {recent.length > 0 && (
        <section>
          <div className="mb-5 flex items-end justify-between">
            <div>
              <div className="kicker">Latest from the desk</div>
              <h2 className="mt-1 font-serif text-[28px] font-semibold tracking-tight">Recently published</h2>
            </div>
            <Link to="/archive" className="flex items-center gap-1 text-[13px] text-muted hover:text-text">
              Full archive <ArrowUpRight size={14} />
            </Link>
          </div>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {recent.map((r, i) => (
              <motion.div key={r.id} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }}>
                <Link to={`/runs/${r.id}`} className="panel group block h-full p-5 transition-colors hover:border-line-2">
                  <div className="mb-3 flex items-center gap-2 font-mono text-[10.5px] uppercase tracking-wider text-dim">
                    <span className="text-accent">{r.source_type}</span>·<span>{timeAgo(r.created_at)}</span>
                  </div>
                  <h3 className="font-serif text-[19px] font-semibold leading-snug group-hover:text-white">{r.headline}</h3>
                  <div className="mt-3 truncate text-[12.5px] text-muted">{r.source_name}</div>
                  <div className="mt-3 flex gap-3 font-mono text-[11px] text-dim">
                    <span>{r.rows?.toLocaleString()} rows</span>
                    <span>{r.n_findings} findings</span>
                    <span>{fmtMs(r.duration_ms)}</span>
                  </div>
                </Link>
              </motion.div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
