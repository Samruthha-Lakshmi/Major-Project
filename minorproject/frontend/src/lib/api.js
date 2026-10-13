async function request(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  health: () => request("/api/health"),
  stats: () => request("/api/stats"),
  samples: () => request("/api/samples"),
  sources: () => request("/api/sources"),
  runs: (limit = 100) => request(`/api/runs?limit=${limit}`),
  run: (id) => request(`/api/runs/${id}`),
  deleteRun: (id) => request(`/api/runs/${id}`, { method: "DELETE" }),
  watchers: () => request("/api/watchers"),
  createWatcher: (body) =>
    request("/api/watchers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteWatcher: (id) => request(`/api/watchers/${id}`, { method: "DELETE" }),
  startRun: ({ mode, file, sample, source, params, narrativeMode, alpha }) => {
    const fd = new FormData();
    fd.append("mode", mode);
    if (file) fd.append("file", file);
    if (sample) fd.append("sample", sample);
    if (source) fd.append("source", source);
    if (params) fd.append("params", JSON.stringify(params));
    fd.append("narrative_mode", narrativeMode);
    fd.append("alpha", String(alpha));
    return request("/api/runs", { method: "POST", body: fd });
  },
};

export const reportUrl = (id, { offline = false, download = false } = {}) => {
  const q = new URLSearchParams();
  if (offline) q.set("offline", "1");
  if (download) q.set("download", "1");
  const s = q.toString();
  return `/api/runs/${id}/report.html${s ? `?${s}` : ""}`;
};

export const wsUrl = (path) => {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${path}`;
};
