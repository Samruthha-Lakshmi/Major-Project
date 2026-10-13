import { useEffect, useReducer, useRef } from "react";
import { api, wsUrl } from "../lib/api";

// The backend often finishes a run in about a second. Events are real, but released to the
// UI with a short minimum gap so each stage is visible as it happens. Replays of archived
// runs use a faster pace, and "skip" flushes everything at once.
const GAP = { stage: 380, finding: 200, chart: 140, preview: 160, story: 120, log: 45, run: 0, complete: 200 };

const initial = {
  status: "connecting",
  run: null,
  stages: {},
  logs: [],
  preview: null,
  findings: [],
  story: null,
  narrativeText: "",
  error: null,
  result: null,
  startedAt: null,
};

function reducer(state, e) {
  switch (e.type) {
    case "reset":
      return { ...initial };
    case "run":
      return { ...state, run: e.run ?? state.run, status: e.status ?? state.status, startedAt: state.startedAt ?? e.ts };
    case "stage":
      return {
        ...state,
        status: state.status === "connecting" || state.status === "queued" ? "running" : state.status,
        startedAt: state.startedAt ?? e.ts,
        stages: { ...state.stages, [e.stage]: { ...state.stages[e.stage], ...e } },
      };
    case "log":
      return { ...state, logs: [...state.logs, e].slice(-400) };
    case "preview":
      return { ...state, preview: { columns: e.columns, rows: e.rows } };
    case "finding":
      return { ...state, findings: [...state.findings, e.finding] };
    case "chart":
      return {
        ...state,
        findings: state.findings.map((f) => (f.id === e.finding_id ? { ...f, chart: e.chart } : f)),
      };
    case "narrative_delta":
      return { ...state, narrativeText: state.narrativeText + e.text };
    case "story":
      return { ...state, story: e.story };
    case "complete":
      return { ...state, status: "done", run: e.run ?? state.run, finishedAt: e.ts };
    case "error":
      return { ...state, status: "error", error: e.message };
    case "result":
      return { ...state, result: e.result, run: e.run ?? state.run };
    default:
      return state;
  }
}

export function useRunStream(runId) {
  const [state, dispatch] = useReducer(reducer, initial);
  const queue = useRef([]);
  const timer = useRef(null);
  const pace = useRef(1);
  const skip = useRef(false);

  useEffect(() => {
    if (!runId) return undefined;
    dispatch({ type: "reset" });
    queue.current = [];
    skip.current = false;
    pace.current = 1;
    let closed = false;
    let replay = false;

    const pump = () => {
      timer.current = null;
      if (closed) return;
      const e = queue.current.shift();
      if (!e) return;
      if (e.type === "eof") {
        if (replay) {
          api.run(runId).then((r) => !closed && dispatch({ type: "result", result: r.result, run: r.run })).catch(() => {});
        }
        return;
      }
      dispatch(e);
      if (e.type === "complete") {
        api.run(runId).then((r) => !closed && dispatch({ type: "result", result: r.result, run: r.run })).catch(() => {});
      }
      const gap = skip.current ? 0 : (GAP[e.type] ?? 0) * pace.current;
      timer.current = setTimeout(pump, gap);
    };
    const enqueue = (e) => {
      queue.current.push(e);
      if (!timer.current) timer.current = setTimeout(pump, 0);
    };

    // Archived runs replay faster than live ones.
    api
      .run(runId)
      .then((r) => {
        if (["done", "error"].includes(r.run.status)) {
          replay = true;
          pace.current = 0.45;
        }
      })
      .catch(() => {});

    const ws = new WebSocket(wsUrl(`/ws/runs/${runId}`));
    ws.onmessage = (m) => {
      const e = JSON.parse(m.data);
      if (e.type === "narrative_delta") {
        dispatch(e); // already naturally paced by the model's stream
        return;
      }
      enqueue(e);
    };
    ws.onerror = () => enqueue({ type: "error", message: "Lost connection to the pipeline server." });
    return () => {
      closed = true;
      clearTimeout(timer.current);
      timer.current = null;
      ws.close();
    };
  }, [runId]);

  const skipAnimation = () => {
    skip.current = true;
  };

  return { ...state, skipAnimation };
}
