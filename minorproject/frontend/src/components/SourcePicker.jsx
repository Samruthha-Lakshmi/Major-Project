import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, CloudSun, Database, Earth, FileSpreadsheet, Landmark, Loader2, Radio, Sparkles, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useFeed } from "../hooks/useFeed";
import { api } from "../lib/api";

const TABS = [
  { id: "live", label: "Live feeds", icon: Radio },
  { id: "sample", label: "Sample data", icon: Database },
  { id: "upload", label: "Upload", icon: Upload },
];
const SOURCE_ICON = { usgs: Earth, weather: CloudSun, worldbank: Landmark };

function Segmented({ value, onChange, options, layoutId }) {
  return (
    <div className="flex rounded-xl border border-line bg-ink/60 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          disabled={o.disabled}
          title={o.title}
          onClick={() => onChange(o.value)}
          className={`relative flex-1 rounded-lg px-3 py-1.5 text-[12.5px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
            value === o.value ? "text-text" : "text-muted hover:text-text"
          }`}
        >
          {value === o.value && (
            <motion.span layoutId={layoutId} className="absolute inset-0 rounded-lg bg-panel-2 ring-1 ring-line-2" transition={{ type: "spring", stiffness: 400, damping: 32 }} />
          )}
          <span className="relative flex items-center justify-center gap-1.5">{o.label}</span>
        </button>
      ))}
    </div>
  );
}

export default function SourcePicker() {
  const navigate = useNavigate();
  const { health } = useFeed();
  const [tab, setTab] = useState("live");
  const [sources, setSources] = useState([]);
  const [samples, setSamples] = useState([]);
  const [selected, setSelected] = useState({ live: "usgs", sample: null });
  const [params, setParams] = useState({});
  const [file, setFile] = useState(null);
  const [drag, setDrag] = useState(false);
  const [narrativeMode, setNarrativeMode] = useState("template");
  const [alpha, setAlpha] = useState(0.05);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const input = useRef(null);

  useEffect(() => {
    api.sources().then((s) => {
      setSources(s);
      setParams(Object.fromEntries(s.map((src) => [src.id, Object.fromEntries(src.params.map((p) => [p.name, p.default]))])));
    }).catch((e) => setError(e.message));
    api.samples().then((s) => {
      setSamples(s);
      setSelected((x) => ({ ...x, sample: s[0]?.id ?? null }));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (health?.llm_available) setNarrativeMode("ai");
  }, [health?.llm_available]);

  const canRun = (tab === "live" && selected.live) || (tab === "sample" && selected.sample) || (tab === "upload" && file);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const { run_id } = await api.startRun({
        mode: tab,
        file: tab === "upload" ? file : null,
        sample: tab === "sample" ? selected.sample : null,
        source: tab === "live" ? selected.live : null,
        params: tab === "live" ? params[selected.live] : null,
        narrativeMode,
        alpha,
      });
      navigate(`/runs/${run_id}`);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <div className="panel relative overflow-hidden p-5 sm:p-6">
      <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-accent/10 blur-3xl" />
      <div className="mb-5 flex items-center justify-between">
        <div>
          <div className="kicker">Newsroom intake</div>
          <div className="mt-1 font-serif text-[22px] font-semibold">Choose a dataset</div>
        </div>
      </div>

      <div className="mb-5 flex gap-1 rounded-2xl border border-line bg-ink/60 p-1">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)} className={`relative flex-1 rounded-xl px-3 py-2 text-[13px] font-medium ${tab === id ? "text-ink" : "text-muted hover:text-text"}`}>
            {tab === id && <motion.span layoutId="src-tab" className="absolute inset-0 rounded-xl bg-text" transition={{ type: "spring", stiffness: 400, damping: 32 }} />}
            <span className="relative flex items-center justify-center gap-2">
              <Icon size={15} />
              {label}
            </span>
          </button>
        ))}
      </div>

      <div className="min-h-[268px]">
        <AnimatePresence mode="wait">
          <motion.div key={tab} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.2 }}>
            {tab === "live" && (
              <div className="space-y-2.5">
                {sources.map((s) => {
                  const Icon = SOURCE_ICON[s.id] ?? Radio;
                  const active = selected.live === s.id;
                  return (
                    <motion.div
                      key={s.id}
                      layout
                      onClick={() => setSelected((x) => ({ ...x, live: s.id }))}
                      className={`cursor-pointer rounded-2xl border p-3.5 transition-colors ${active ? "border-accent/50 bg-accent/[0.06]" : "border-line hover:border-line-2"}`}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${active ? "bg-accent text-ink" : "bg-panel-2 text-muted"}`}>
                          <Icon size={18} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 text-[14px] font-semibold">
                            {s.name}
                            {s.refreshable && <span className="rounded bg-teal/15 px-1.5 font-mono text-[9.5px] text-teal">REAL-TIME</span>}
                          </div>
                          <div className="text-[12.5px] text-muted">{s.description}</div>
                          <AnimatePresence>
                            {active && (
                              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                                <div className="flex flex-wrap gap-3 pt-3">
                                  {s.params.map((p) => (
                                    <label key={p.name} className="flex items-center gap-2 text-[12px] text-muted" onClick={(e) => e.stopPropagation()}>
                                      {p.label}
                                      <select
                                        value={params[s.id]?.[p.name] ?? p.default}
                                        onChange={(e) => setParams((x) => ({ ...x, [s.id]: { ...x[s.id], [p.name]: e.target.value } }))}
                                        className="max-w-[230px] rounded-lg border border-line-2 bg-panel-2 px-2 py-1 text-[12px] text-text outline-none focus:border-accent"
                                      >
                                        {p.options.map((o) => (
                                          <option key={o} value={o}>
                                            {p.labels?.[o] ?? o.replace(/_/g, " ")}
                                          </option>
                                        ))}
                                      </select>
                                    </label>
                                  ))}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            )}

            {tab === "sample" && (
              <div className="space-y-2.5">
                {samples.map((s) => {
                  const active = selected.sample === s.id;
                  return (
                    <div
                      key={s.id}
                      onClick={() => setSelected((x) => ({ ...x, sample: s.id }))}
                      className={`cursor-pointer rounded-2xl border p-3.5 transition-colors ${active ? "border-accent/50 bg-accent/[0.06]" : "border-line hover:border-line-2"}`}
                    >
                      <div className="flex items-center gap-2">
                        <FileSpreadsheet size={16} className={active ? "text-accent" : "text-muted"} />
                        <span className="text-[14px] font-semibold">{s.name}</span>
                        <span className="ml-auto font-mono text-[10.5px] text-dim">
                          {s.rows.toLocaleString()} × {s.cols}
                        </span>
                      </div>
                      <div className="mt-1 text-[12.5px] text-muted">{s.description}</div>
                    </div>
                  );
                })}
                {!samples.length && <p className="text-[13px] text-muted">No samples found — run backend/scripts/make_samples.py.</p>}
              </div>
            )}

            {tab === "upload" && (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDrag(true);
                }}
                onDragLeave={() => setDrag(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDrag(false);
                  if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
                }}
                onClick={() => input.current?.click()}
                className={`relative grid h-[260px] cursor-pointer place-items-center rounded-2xl border-2 border-dashed transition-colors ${
                  drag ? "border-accent bg-accent/[0.06]" : "border-line-2 hover:border-muted"
                }`}
              >
                <input
                  ref={input}
                  type="file"
                  accept=".csv,.tsv,.txt,.xlsx,.xls,.json,.geojson"
                  className="hidden"
                  onChange={(e) => e.target.files[0] && setFile(e.target.files[0])}
                />
                <div className="text-center">
                  <motion.div animate={{ y: drag ? -6 : 0 }} className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-panel-2">
                    <Upload size={22} className={drag ? "text-accent" : "text-muted"} />
                  </motion.div>
                  {file ? (
                    <>
                      <div className="text-[14px] font-semibold">{file.name}</div>
                      <div className="font-mono text-[11px] text-muted">{(file.size / 1024).toFixed(0)} KB · click to change</div>
                    </>
                  ) : (
                    <>
                      <div className="text-[14px] font-semibold">Drop a dataset here</div>
                      <div className="text-[12.5px] text-muted">CSV, TSV, Excel or JSON · up to 50 MB</div>
                    </>
                  )}
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div>
          <div className="kicker mb-1.5">Narrative engine</div>
          <Segmented
            layoutId="seg-engine"
            value={narrativeMode}
            onChange={setNarrativeMode}
            options={[
              { value: "template", label: "Statistical" },
              {
                value: "ai",
                label: (
                  <>
                    <Sparkles size={13} /> Claude AI
                  </>
                ),
                disabled: !health?.llm_available,
                title: health?.llm_available ? "AI narrative, fact-checked against the statistics" : "Set ANTHROPIC_API_KEY in backend/.env to enable",
              },
            ]}
          />
        </div>
        <div>
          <div className="kicker mb-1.5">Significance level α</div>
          <Segmented
            layoutId="seg-alpha"
            value={alpha}
            onChange={setAlpha}
            options={[0.01, 0.05, 0.1].map((a) => ({ value: a, label: a.toFixed(2) }))}
          />
        </div>
      </div>

      <AnimatePresence>
        {error && (
          <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0 }} className="mt-3 text-[13px] text-accent">
            {error}
          </motion.p>
        )}
      </AnimatePresence>

      <motion.button
        whileHover={canRun && !busy ? { scale: 1.015 } : {}}
        whileTap={canRun && !busy ? { scale: 0.98 } : {}}
        disabled={!canRun || busy}
        onClick={run}
        className="group relative mt-5 flex w-full items-center justify-center gap-2 overflow-hidden rounded-2xl bg-accent px-5 py-3.5 text-[15px] font-semibold text-ink disabled:opacity-40"
      >
        <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/30 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
        {busy ? <Loader2 size={18} className="animate-spin" /> : null}
        {busy ? "Starting pipeline…" : "Run the pipeline"}
        {!busy && <ArrowRight size={18} className="transition-transform group-hover:translate-x-1" />}
      </motion.button>
    </div>
  );
}
