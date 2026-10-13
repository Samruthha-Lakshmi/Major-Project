import { motion } from "motion/react";
import { Link } from "react-router-dom";
import { useFeed } from "../hooks/useFeed";

/** Breaking-news style marquee of the latest published headlines. */
export default function Ticker() {
  const { runs } = useFeed();
  const items = runs.filter((r) => r.status === "done" && r.headline).slice(0, 12);
  if (!items.length) return null;
  const loop = [...items, ...items];
  return (
    <div className="relative flex h-8 items-center overflow-hidden border-t border-line bg-panel/40 text-[12px]">
      <div className="z-10 flex h-full shrink-0 items-center gap-2 bg-accent px-3 font-mono text-[10.5px] font-semibold tracking-[0.14em] text-ink">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink" />
        LATEST
      </div>
      <div className="pointer-events-none absolute inset-y-0 left-[84px] z-10 w-10 bg-gradient-to-r from-ink to-transparent" />
      <motion.div
        className="flex shrink-0 gap-10 whitespace-nowrap pl-6"
        animate={{ x: ["0%", "-50%"] }}
        transition={{ duration: Math.max(30, items.length * 9), ease: "linear", repeat: Infinity }}
      >
        {loop.map((r, i) => (
          <Link key={`${r.id}-${i}`} to={`/runs/${r.id}`} className="flex items-center gap-3 text-muted transition-colors hover:text-text">
            <span className="font-mono text-[10px] uppercase tracking-wider text-dim">{r.source_type}</span>
            <span className="font-serif text-[13.5px] text-text/90">{r.headline}</span>
            <span className="text-accent">◆</span>
          </Link>
        ))}
      </motion.div>
    </div>
  );
}
