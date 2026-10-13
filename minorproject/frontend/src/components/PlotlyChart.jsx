import { useEffect, useRef, useState } from "react";

let plotlyPromise;
const loadPlotly = () => {
  plotlyPromise ??= import("plotly.js-dist-min").then((m) => m.default ?? m);
  return plotlyPromise;
};

const DARK = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: "Inter, system-ui, sans-serif", color: "#c9c8c4", size: 12 },
};

/** Renders a backend Plotly figure spec with the app's dark styling. Plotly is lazy-loaded. */
export default function PlotlyChart({ figure, height = 340, hideTitle = true }) {
  const ref = useRef(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!figure || !ref.current) return undefined;
    let cancelled = false;
    let observer;
    loadPlotly().then((Plotly) => {
      if (cancelled || !ref.current) return;
      const l = figure.layout || {};
      const axis = (a) => ({
        ...a,
        gridcolor: "rgba(255,255,255,0.06)",
        linecolor: "rgba(255,255,255,0.12)",
        tickfont: { color: "#8b919b" },
        title: a?.title ? { ...(typeof a.title === "string" ? { text: a.title } : a.title), font: { color: "#8b919b", size: 11 } } : a?.title,
      });
      const layout = {
        ...l,
        ...DARK,
        title: hideTitle ? undefined : l.title,
        margin: { ...(l.margin || {}), t: hideTitle ? 16 : 48 },
        xaxis: axis(l.xaxis),
        yaxis: axis(l.yaxis),
        height,
        autosize: true,
        hoverlabel: { bgcolor: "#171a1f", bordercolor: "#2a2e35", font: { family: "JetBrains Mono, monospace", color: "#ecebe7" } },
        legend: { ...(l.legend || {}), font: { color: "#8b919b" } },
      };
      Plotly.react(ref.current, figure.data, layout, {
        responsive: true,
        displaylogo: false,
        modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
      });
      setReady(true);
      observer = new ResizeObserver(() => ref.current && Plotly.Plots.resize(ref.current));
      observer.observe(ref.current);
    });
    return () => {
      cancelled = true;
      observer?.disconnect();
    };
  }, [figure, height, hideTitle]);

  return (
    <div className="relative" style={{ height }}>
      {!ready && (
        <div className="absolute inset-0 grid place-items-center">
          <span className="kicker shimmer">Rendering chart</span>
        </div>
      )}
      <div ref={ref} className="h-full w-full" />
    </div>
  );
}
