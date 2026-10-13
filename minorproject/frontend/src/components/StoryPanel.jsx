import { motion } from "motion/react";
import { ShieldCheck, Sparkles } from "lucide-react";

/** The generated story: streams Claude's draft live, then shows the fact-checked final copy. */
export default function StoryPanel({ story, streaming, stage }) {
  if (!story && !streaming && stage !== "running") return null;

  if (!story) {
    return (
      <div className="panel p-6">
        <div className="mb-3 flex items-center gap-2">
          <Sparkles size={15} className="text-violet" />
          <span className="kicker">Narrative engine · drafting</span>
        </div>
        {streaming ? (
          <p className="caret whitespace-pre-wrap font-serif text-[16px] leading-relaxed text-text/85">{streaming}</p>
        ) : (
          <p className="kicker shimmer">Writing from validated findings…</p>
        )}
      </div>
    );
  }

  const v = story.verification;
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="panel relative overflow-hidden p-6 sm:p-8">
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-accent via-amber to-teal" />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="kicker !text-accent">The story</span>
        <span className="rounded-full border border-line px-2 py-0.5 font-mono text-[10.5px] text-muted">
          {story.engine === "ai" ? `Claude · ${story.model ?? ""}` : "Statistical narrative engine"}
        </span>
        {v && v.checked > 0 && (
          <span className="flex items-center gap-1 rounded-full bg-teal/10 px-2 py-0.5 font-mono text-[10.5px] text-teal">
            <ShieldCheck size={12} /> {v.verified}/{v.checked} passages fact-checked
          </span>
        )}
      </div>
      <motion.h2
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="font-serif text-[30px] font-extrabold leading-[1.1] tracking-tight sm:text-[38px]"
      >
        {story.headline}
      </motion.h2>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
        className="mt-3 font-serif text-[18px] leading-relaxed text-muted"
      >
        {story.standfirst}
      </motion.p>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="mt-5 border-l-2 border-accent pl-4 text-[15.5px] leading-relaxed text-text/90"
      >
        {story.lede}
      </motion.p>
      {v?.details?.some((d) => d.status !== "verified") && (
        <div className="mt-5 rounded-xl border border-amber/25 bg-amber/5 p-3 text-[12.5px] text-amber/90">
          Fact-check replaced {v.details.filter((d) => d.status !== "verified").length} AI passage(s) with the
          statistical version because they contained numbers that could not be traced to the analysis
          {v.details.find((d) => d.numbers) ? ` (e.g. ${v.details.find((d) => d.numbers).numbers.slice(0, 3).join(", ")})` : ""}.
        </div>
      )}
      {story.caveats?.length > 0 && (
        <ul className="mt-5 space-y-1.5 text-[12.5px] text-muted">
          {story.caveats.map((c) => (
            <li key={c} className="flex gap-2">
              <span className="text-dim">—</span>
              {c}
            </li>
          ))}
        </ul>
      )}
    </motion.div>
  );
}
