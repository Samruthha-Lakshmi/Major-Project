import { AnimatePresence, motion } from "motion/react";
import { Terminal } from "lucide-react";
import { useEffect, useRef } from "react";

const LEVEL = { info: "text-muted", warning: "text-amber", error: "text-accent" };

/** Live log stream from the pipeline worker. */
export default function Console({ logs, status }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [logs.length]);

  return (
    <div className="panel flex h-[360px] flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <Terminal size={14} className="text-muted" />
        <span className="kicker">Pipeline log</span>
        <span className="ml-auto flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-[#3a3f47]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#3a3f47]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#3a3f47]" />
        </span>
      </div>
      <div ref={ref} className="flex-1 overflow-y-auto px-4 py-3 font-mono text-[11.5px] leading-[1.7]">
        <AnimatePresence initial={false}>
          {logs.map((l, i) => (
            <motion.div
              key={`${l.ts}-${i}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="flex gap-2"
            >
              <span className="w-[68px] shrink-0 text-dim">{l.stage}</span>
              <span className={LEVEL[l.level] ?? "text-muted"}>{l.message}</span>
            </motion.div>
          ))}
        </AnimatePresence>
        {status === "running" && <div className="caret mt-1 text-dim">&nbsp;</div>}
      </div>
    </div>
  );
}
