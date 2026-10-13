export const STAGES = [
  { id: "ingest", name: "Ingestion", long: "Ingestion & Validation", tech: "Python · Pandas", desc: "Load the dataset and verify schema and types" },
  { id: "preprocess", name: "Preprocess", long: "Preprocessing", tech: "Pandas · NumPy", desc: "Handle missing values, duplicates and outliers" },
  { id: "eda", name: "Explore", long: "Exploratory Analysis", tech: "Pandas · SciPy", desc: "Profile structure, distributions and the time axis" },
  { id: "stats", name: "Statistics", long: "Statistical Analysis", tech: "SciPy · Statsmodels", desc: "Correlation, t-test/ANOVA, χ², trend — with FDR control" },
  { id: "insights", name: "Insights", long: "Insight & Anomaly Detection", tech: "Scikit-learn", desc: "Rank findings; Isolation Forest and robust z-scores" },
  { id: "viz", name: "Visualize", long: "Visualization", tech: "Plotly", desc: "Recommend and build the right chart for each finding" },
  { id: "narrative", name: "Narrative", long: "Narrative Generation", tech: "Templates · Claude", desc: "Turn validated findings into fact-checked news copy" },
  { id: "report", name: "Publish", long: "HTML Report", tech: "Jinja2 · HTML/CSS/JS", desc: "Assemble the publication-ready news report" },
];

export function fmtNum(v, digits = 3) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (a >= 1e4) return Math.round(v).toLocaleString();
  if (a >= 100) return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (a === 0) return "0";
  if (Number.isInteger(v)) return String(v);
  if (a >= 1) return v.toFixed(2).replace(/\.?0+$/, "");
  return Number(v.toPrecision(digits)).toString();
}

export function fmtP(p) {
  if (p === null || p === undefined) return "—";
  if (p < 0.001) return "< 0.001";
  return p.toFixed(3);
}

export function fmtMs(ms) {
  if (ms === null || ms === undefined) return "";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function timeAgo(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const s = Math.round((Date.now() - d.getTime()) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function humanize(col) {
  return String(col)
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .trim();
}

export const KIND_META = {
  trend: { label: "Trend", color: "#ff5a36" },
  group_difference: { label: "Group gap", color: "#f2b134" },
  correlation: { label: "Correlation", color: "#1fb5a8" },
  association: { label: "Association", color: "#8f7cff" },
  spike: { label: "Spike", color: "#ff8fb1" },
  anomaly: { label: "Anomaly", color: "#ff5a36" },
  concentration: { label: "Concentration", color: "#47c97a" },
};

export const SEMANTIC_COLOR = {
  numeric: "#1fb5a8",
  categorical: "#f2b134",
  datetime: "#8f7cff",
  boolean: "#ff8fb1",
  text: "#8b919b",
  id: "#5c626c",
};
