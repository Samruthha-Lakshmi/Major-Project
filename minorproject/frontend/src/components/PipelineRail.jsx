import { AnimatePresence, motion } from "motion/react";
import { STAGES, fmtMs } from "../lib/format";

function Check() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4">
      <motion.path
        d="M5 12.5l4.5 4.5L19 7.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
      />
    </svg>
  );
}

function headline(stage, s) {
  const x = s?.summary || {};
  switch (stage) {
    case "ingest":
      return x.rows !== undefined ? `${x.rows.toLocaleString()} × ${x.cols}` : null;
    case "preprocess":
      return x.rows_out !== undefined ? `${x.duplicates} dup · ${x.imputed} filled` : null;
    case "eda":
      return x.numeric !== undefined ? `${x.numeric} measures${x.unit ? ` · by ${x.unit}` : ""}` : null;
    case "stats":
      return x.n_tests !== undefined ? `${x.n_significant}/${x.n_tests} significant` : null;
    case "insights":
      return x.findings !== undefined ? `${x.findings} findings` : null;
    case "viz":
      return x.charts !== undefined ? `${x.charts} charts` : null;
    case "narrative":
      return x.engine ? (x.engine === "ai" ? `Claude · ${x.verification ?? 0} verified` : "Statistical") : null;
    case "report":
      return x.bytes ? `${Math.round(x.bytes / 1024)} KB HTML` : null;
    default:
      return null;
  }
}

/** The eight pipeline stages as an animated, connected rail that fills as the run progresses. */
export default function PipelineRail({ stages, compact = false }) {
  const doneCount = STAGES.filter((s) => stages[s.id]?.status === "done").length;
  const runningIdx = STAGES.findIndex((s) => stages[s.id]?.status === "running");
  // Fill reaches the centre of the running node (or the last finished one).
  const pos = runningIdx >= 0 ? runningIdx : Math.max(doneCount - 1, 0);
  const fill = pos / (STAGES.length - 1);

  return (
    <div className="panel relative overflow-hidden p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between">
        <span className="kicker">Pipeline</span>
        <span className="font-mono text-[11px] text-muted tabular">
          {doneCount}/{STAGES.length} stages
        </span>
      </div>
      <div className="relative">
        {/* track */}
        <div className="absolute left-[6.25%] right-[6.25%] top-[19px] hidden h-[2px] rounded bg-line-2 md:block" />
        <motion.div
          className="absolute left-[6.25%] top-[19px] hidden h-[2px] origin-left rounded bg-gradient-to-r from-accent via-amber to-teal md:block"
          style={{ width: "87.5%" }}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: fill }}
          transition={{ type: "spring", stiffness: 60, damping: 18 }}
        />
        <ol className="relative grid grid-cols-4 gap-y-5 md:grid-cols-8">
          {STAGES.map((st, i) => {
            const s = stages[st.id];
            const status = s?.status ?? "pending";
            const h = headline(st.id, s);
            return (
              <li key={st.id} className="flex flex-col items-center px-1 text-center">
                <div className="relative grid h-10 w-10 place-items-center">
                  {status === "running" && (
                    <>
                      <motion.span
                        className="absolute inset-0 rounded-full border-2 border-accent"
                        animate={{ scale: [1, 1.55], opacity: [0.7, 0] }}
                        transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
                      />
                      <motion.span
                        className="absolute inset-0 rounded-full border-2 border-transparent border-t-accent"
                        animate={{ rotate: 360 }}
                        transition={{ duration: 0.9, repeat: Infinity, ease: "linear" }}
                      />
                    </>
                  )}
                  <motion.div
                    layout
                    animate={{
                      scale: status === "running" ? 1.08 : 1,
                      backgroundColor:
                        status === "done" ? "#1fb5a8" : status === "running" ? "#ff5a36" : status === "error" ? "#c0392b" : "#171a1f",
                    }}
                    transition={{ type: "spring", stiffness: 300, damping: 20 }}
                    className={`relative grid h-9 w-9 place-items-center rounded-full border font-mono text-[12px] font-semibold ${
                      status === "pending" ? "border-line-2 text-dim" : "border-transparent text-ink"
                    }`}
                  >
                    {status === "done" ? <Check /> : status === "error" ? "!" : i + 1}
                  </motion.div>
                </div>
                <div className={`mt-2 text-[12.5px] font-semibold ${status === "pending" ? "text-dim" : "text-text"}`}>{st.name}</div>
                {!compact && <div className="hidden text-[10.5px] text-dim lg:block">{st.tech}</div>}
                <div className="h-8">
                  <AnimatePresence>
                    {status === "done" && (
                      <motion.div
                        initial={{ opacity: 0, y: 6, scale: 0.9 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        className="mt-1 flex flex-col items-center"
                      >
                        {h && <span className="rounded-md bg-panel-2 px-1.5 py-0.5 font-mono text-[10.5px] text-text/90">{h}</span>}
                        <span className="mt-0.5 font-mono text-[10px] text-dim">{fmtMs(s.ms)}</span>
                      </motion.div>
                    )}
                    {status === "running" && (
                      <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="kicker shimmer mt-1 block !text-[10px]">
                        working
                      </motion.span>
                    )}
                  </AnimatePresence>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
