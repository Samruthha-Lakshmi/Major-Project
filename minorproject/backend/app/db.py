"""SQLite persistence for pipeline runs, their results and generated reports."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any

from .config import DB_PATH

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    finished_at   TEXT,
    status        TEXT NOT NULL,
    source_type   TEXT NOT NULL,
    source_name   TEXT NOT NULL,
    narrative_mode TEXT NOT NULL,
    rows          INTEGER,
    cols          INTEGER,
    n_findings    INTEGER,
    headline      TEXT,
    duration_ms   INTEGER,
    watcher_id    TEXT,
    error         TEXT
);
CREATE TABLE IF NOT EXISTS run_results (
    run_id  TEXT PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    result  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_events (
    run_id  TEXT PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    events  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    run_id  TEXT PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    html    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_created ON runs(created_at DESC);
"""


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with _lock, connect() as conn:
        conn.executescript(SCHEMA)
        # Runs interrupted by a server restart can never finish.
        conn.execute("UPDATE runs SET status='error', error='Interrupted by server restart' "
                     "WHERE status IN ('queued','running')")


def insert_run(row: dict[str, Any]) -> None:
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    with _lock, connect() as conn:
        conn.execute(f"INSERT INTO runs ({cols}) VALUES ({marks})", list(row.values()))


def update_run(run_id: str, **fields: Any) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    with _lock, connect() as conn:
        conn.execute(f"UPDATE runs SET {sets} WHERE id=?", [*fields.values(), run_id])


def save_outputs(run_id: str, result: dict, events: list[dict], html: str | None) -> None:
    with _lock, connect() as conn:
        conn.execute("INSERT OR REPLACE INTO run_results VALUES (?, ?)", (run_id, json.dumps(result)))
        conn.execute("INSERT OR REPLACE INTO run_events VALUES (?, ?)", (run_id, json.dumps(events)))
        if html is not None:
            conn.execute("INSERT OR REPLACE INTO reports VALUES (?, ?)", (run_id, html))


def save_events(run_id: str, events: list[dict]) -> None:
    with _lock, connect() as conn:
        conn.execute("INSERT OR REPLACE INTO run_events VALUES (?, ?)", (run_id, json.dumps(events)))


def list_runs(limit: int = 100) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_run(run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    return dict(row) if row else None


def get_result(run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT result FROM run_results WHERE run_id=?", (run_id,)).fetchone()
    return json.loads(row["result"]) if row else None


def get_events(run_id: str) -> list[dict]:
    with connect() as conn:
        row = conn.execute("SELECT events FROM run_events WHERE run_id=?", (run_id,)).fetchone()
    return json.loads(row["events"]) if row else []


def get_report(run_id: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT html FROM reports WHERE run_id=?", (run_id,)).fetchone()
    return row["html"] if row else None


def delete_run(run_id: str) -> bool:
    with _lock, connect() as conn:
        cur = conn.execute("DELETE FROM runs WHERE id=?", (run_id,))
    return cur.rowcount > 0


def stats() -> dict:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS runs, COALESCE(SUM(rows),0) AS rows_analysed, "
            "COALESCE(SUM(n_findings),0) AS findings, "
            "COALESCE(AVG(CASE WHEN status='done' THEN duration_ms END),0) AS avg_ms "
            "FROM runs").fetchone()
    return dict(row)
