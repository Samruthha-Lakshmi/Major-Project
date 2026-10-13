import { motion } from "motion/react";
import { STAGES } from "../lib/format";

const TESTS = [
  ["Numeric × numeric", "Pearson r, with Spearman ρ as a rank-based robustness check", "r"],
  ["Category × numeric (2 groups)", "Welch t-test, or Mann–Whitney U when groups are small and non-normal", "Cohen's d"],
  ["Category × numeric (3+ groups)", "One-way ANOVA, or Kruskal–Wallis H", "η²"],
  ["Category × category", "χ² test of independence", "Cramér's V"],
  ["Time × numeric", "Kendall τ trend test plus an OLS slope (statsmodels) on the resampled series", "τ"],
  ["Anomalies", "Robust z-score (median/MAD > 3.5), Isolation Forest, rolling-median residual spikes", "z"],
];

const STACK = [
  ["Data processing", "Pandas · NumPy"],
  ["Statistics", "SciPy · Statsmodels"],
  ["Anomaly detection", "Scikit-learn (Isolation Forest, RobustScaler)"],
  ["Visualization", "Plotly (Python → plotly.js)"],
  ["Narrative", "Deterministic NLG templates · Claude (Anthropic API) with numeric fact-check"],
  ["Report", "Jinja2 · HTML/CSS/JS, responsive, light & dark, printable"],
  ["API & real-time", "FastAPI · WebSockets · asyncio"],
  ["Storage", "SQLite (runs, results, event logs, reports)"],
  ["Interface", "React · Motion (motion.dev) · Tailwind CSS · Vite"],
];

function Reveal({ children, delay = 0 }) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-60px" }} transition={{ delay, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}>
      {children}
    </motion.div>
  );
}

export default function Method() {
  return (
    <div className="mx-auto max-w-5xl space-y-16">
      <Reveal>
        <div className="kicker">Methodology</div>
        <h1 className="mt-2 font-serif text-[40px] font-extrabold leading-tight tracking-tight sm:text-[56px]">
          Statistics drive the story — <span className="italic text-accent">not the other way round.</span>
        </h1>
        <p className="mt-4 max-w-3xl text-[16.5px] leading-relaxed text-muted">
          Most automated-journalism systems optimise one stage in isolation. This pipeline integrates the full workflow, and
          every sentence in a published report can be traced back to a statistical test that survived correction for multiple
          comparisons.
        </p>
      </Reveal>

      <section>
        <Reveal>
          <h2 className="mb-6 font-serif text-[28px] font-semibold">System architecture</h2>
        </Reveal>
        <div className="relative space-y-3 pl-8">
          <div className="absolute bottom-4 left-[13px] top-4 w-px bg-gradient-to-b from-accent via-amber to-teal" />
          {STAGES.map((s, i) => (
            <Reveal key={s.id} delay={i * 0.04}>
              <div className="relative">
                <span className="absolute -left-8 top-4 grid h-[26px] w-[26px] place-items-center rounded-full border border-line-2 bg-ink font-mono text-[11px]">{i + 1}</span>
                <div className="panel flex flex-wrap items-center justify-between gap-2 px-5 py-4">
                  <div>
                    <div className="text-[15.5px] font-semibold">{s.long}</div>
                    <div className="text-[13px] text-muted">{s.desc}</div>
                  </div>
                  <span className="rounded-full bg-panel-2 px-3 py-1 font-mono text-[11px] text-accent">{s.tech}</span>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section>
        <Reveal>
          <h2 className="mb-2 font-serif text-[28px] font-semibold">The test family</h2>
          <p className="mb-6 text-[14.5px] text-muted">
            Every sensible column pair is tested. All p-values are then adjusted together with the Benjamini–Hochberg procedure,
            and a finding is only reported if its q-value is below α <em>and</em> its effect size is non-negligible.
          </p>
        </Reveal>
        <div className="panel divide-y divide-line">
          {TESTS.map(([pair, method, effect], i) => (
            <Reveal key={pair} delay={i * 0.04}>
              <div className="grid gap-1 px-5 py-4 sm:grid-cols-[220px_1fr_90px] sm:gap-4">
                <span className="text-[14px] font-semibold">{pair}</span>
                <span className="text-[13.5px] text-muted">{method}</span>
                <span className="font-mono text-[12px] text-teal sm:text-right">{effect}</span>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <Reveal>
          <div className="panel h-full p-6">
            <h3 className="font-serif text-[22px] font-semibold">Newsworthiness ranking</h3>
            <p className="mt-2 text-[14px] leading-relaxed text-muted">
              Each finding is scored as 35% statistical strength (−log₁₀ q), 35% normalised effect size and 30% story type
              (trends and spikes rank above static correlations). Tautologies are filtered out — near-identical measures
              (|r| &gt; 0.98) and categories cut directly from a measure (non-overlapping ranges). No column may dominate more
              than three findings.
            </p>
          </div>
        </Reveal>
        <Reveal delay={0.08}>
          <div className="panel h-full p-6">
            <h3 className="font-serif text-[22px] font-semibold">Fact-checked AI narrative</h3>
            <p className="mt-2 text-[14px] leading-relaxed text-muted">
              Claude only sees validated findings and is told to use only their numbers. Its draft streams live, then every
              number it wrote is matched against the verified facts (to displayed precision). Any passage with an untraceable
              number is replaced by the deterministic statistical version, and the swap is shown in the report.
            </p>
          </div>
        </Reveal>
      </section>

      <section>
        <Reveal>
          <h2 className="mb-6 font-serif text-[28px] font-semibold">Technology stack</h2>
        </Reveal>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {STACK.map(([k, v], i) => (
            <Reveal key={k} delay={i * 0.03}>
              <div className="panel h-full p-4">
                <div className="kicker">{k}</div>
                <div className="mt-1.5 text-[14px]">{v}</div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <Reveal>
        <section className="panel p-6 sm:p-8">
          <div className="kicker">Project</div>
          <h3 className="mt-2 font-serif text-[22px] font-semibold leading-snug">
            Automated Data Journalism Pipeline for Statistical Analysis and HTML News Report Generation
          </h3>
          <div className="mt-4 grid gap-4 text-[14px] sm:grid-cols-3">
            <div>
              <div className="text-dim">Department</div>Artificial Intelligence and Data Science
            </div>
            <div>
              <div className="text-dim">Institution</div>Dhanalakshmi College of Engineering
            </div>
            <div>
              <div className="text-dim">Academic year</div>2025 – 2026
            </div>
            <div>
              <div className="text-dim">Guided by</div>Dr K Dhinakaran, B.E., M.E., Ph.D
            </div>
            <div>
              <div className="text-dim">Presented by</div>Yuvanesh R
            </div>
          </div>
        </section>
      </Reveal>
    </div>
  );
}
