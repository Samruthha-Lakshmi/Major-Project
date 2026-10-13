import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, wsUrl } from "../lib/api";

const FeedContext = createContext(null);

/** One WebSocket per tab carrying newsroom-wide events: runs starting/finishing and watcher updates. */
export function FeedProvider({ children }) {
  const [connected, setConnected] = useState(false);
  const [runs, setRuns] = useState([]);
  const [watchers, setWatchers] = useState({});
  const [wire, setWire] = useState([]);
  const [health, setHealth] = useState(null);
  const retry = useRef(0);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api.runs(60).then(setRuns).catch(() => {});
  }, []);

  useEffect(() => {
    let ws;
    let stop = false;
    let reconnect;
    const connect = () => {
      ws = new WebSocket(wsUrl("/ws/feed"));
      ws.onopen = () => {
        setConnected(true);
        retry.current = 0;
      };
      ws.onclose = () => {
        setConnected(false);
        if (!stop) reconnect = setTimeout(connect, Math.min(1000 * 2 ** retry.current++, 15000));
      };
      ws.onmessage = (m) => {
        const e = JSON.parse(m.data);
        if (e.type === "hello") {
          setWatchers(Object.fromEntries(e.watchers.map((w) => [w.id, w])));
          return;
        }
        if (e.type === "ping") return;
        if (e.type === "run_started" || e.type === "run_finished") {
          setRuns((rs) => [e.run, ...rs.filter((r) => r.id !== e.run.id)].slice(0, 100));
        }
        if (e.type === "run_deleted") setRuns((rs) => rs.filter((r) => r.id !== e.run_id));
        if (e.type === "watcher") setWatchers((ws_) => ({ ...ws_, [e.watcher.id]: e.watcher }));
        if (e.type === "watcher_removed")
          setWatchers((ws_) => {
            const n = { ...ws_ };
            delete n[e.id];
            return n;
          });
        setWire((w) => [{ ...e, key: `${e.ts}-${Math.random()}` }, ...w].slice(0, 60));
      };
    };
    connect();
    return () => {
      stop = true;
      clearTimeout(reconnect);
      ws?.close();
    };
  }, []);

  return (
    <FeedContext.Provider value={{ connected, runs, setRuns, watchers, setWatchers, wire, health }}>
      {children}
    </FeedContext.Provider>
  );
}

export const useFeed = () => useContext(FeedContext);
