"""FastAPI application: REST API, WebSocket event streams and the live-desk watchers."""
from __future__ import annotations

import asyncio
import json
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, db, jsonutil
from .config import (ANTHROPIC_MODEL, CORS_ORIGINS, DEFAULT_ALPHA, FRONTEND_DIST, MAX_UPLOAD_MB,
                     SAMPLES_DIR, llm_available)
from .events import bus
from .pipeline import STAGES, ingest, report, runner
from .sources import live

MAX_CONCURRENT_RUNS = 3
_run_slots: asyncio.Semaphore
_run_done: dict[str, asyncio.Future] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _run_slots
    db.init()
    bus.bind_loop(asyncio.get_running_loop())
    _run_slots = asyncio.Semaphore(MAX_CONCURRENT_RUNS)
    yield
    for w in list(watchers.values()):
        w["task"].cancel()


app = FastAPI(title="Automated Data Journalism Pipeline", version=__version__, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


# ============================================================================ runs
def _samples() -> list[dict]:
    index = SAMPLES_DIR / "index.json"
    if not index.exists():
        return []
    items = json.loads(index.read_text(encoding="utf-8"))
    return [s for s in items if (SAMPLES_DIR / s["file"]).exists()]


def _row_public(row: dict) -> dict:
    return {k: row[k] for k in ("id", "created_at", "finished_at", "status", "source_type", "source_name",
                                "narrative_mode", "rows", "cols", "n_findings", "headline", "duration_ms",
                                "watcher_id", "error")}


async def start_run(source_type: str, source_name: str, loader, options: dict,
                    watcher_id: str | None = None) -> str:
    run_id = uuid.uuid4().hex
    row = {"id": run_id, "created_at": datetime.now().isoformat(timespec="seconds"), "status": "queued",
           "source_type": source_type, "source_name": source_name,
           "narrative_mode": options["narrative_mode"], "watcher_id": watcher_id}
    db.insert_run(row)
    channel = f"run:{run_id}"
    stored: list[dict] = []
    lock = threading.Lock()

    def emit(event: dict) -> None:
        event = jsonutil.clean(event)
        if event.get("type") != "narrative_delta":
            with lock:
                stored.append(event)
        bus.publish(channel, event)

    loop = asyncio.get_running_loop()
    done: asyncio.Future = loop.create_future()
    _run_done[run_id] = done
    emit({"type": "run", "status": "queued", "run": _row_public({**db.get_run(run_id)})})
    bus.publish("feed", {"type": "run_started", "run": _row_public(db.get_run(run_id))})

    async def task():
        async with _run_slots:
            db.update_run(run_id, status="running")
            emit({"type": "run", "status": "running"})
            try:
                result, html = await asyncio.to_thread(runner.run, run_id, loader, options, emit)
                result = jsonutil.clean(result)
                fields = dict(status="done", finished_at=datetime.now().isoformat(timespec="seconds"),
                              rows=result["profile"]["rows"], cols=result["ingest"]["cols"],
                              n_findings=len(result["findings"]), headline=result["story"]["headline"],
                              duration_ms=result["duration_ms"],
                              source_name=result["source"]["name"])
                db.update_run(run_id, **fields)
                emit({"type": "complete", "run": _row_public(db.get_run(run_id))})
                db.save_outputs(run_id, result, stored, html)
            except Exception as exc:
                msg = runner.format_error(exc)
                db.update_run(run_id, status="error", error=msg.splitlines()[0][:500],
                              finished_at=datetime.now().isoformat(timespec="seconds"))
                emit({"type": "error", "message": msg.splitlines()[0]})
                db.save_events(run_id, stored)
            finally:
                bus.close(channel)
                bus.publish("feed", {"type": "run_finished", "run": _row_public(db.get_run(run_id))})
                if not done.done():
                    done.set_result(run_id)
                # Keep the replay buffer briefly for late subscribers, then serve from SQLite.
                await asyncio.sleep(120)
                bus.forget(channel)
                _run_done.pop(run_id, None)

    asyncio.create_task(task())
    return run_id


def _options(narrative_mode: str, alpha: float) -> dict:
    if narrative_mode not in ("template", "ai"):
        raise HTTPException(400, "narrative_mode must be 'template' or 'ai'")
    if not 0.001 <= alpha <= 0.2:
        raise HTTPException(400, "alpha must be between 0.001 and 0.2")
    return {"narrative_mode": narrative_mode, "alpha": alpha}


@app.post("/api/runs")
async def create_run(
    mode: str = Form(...),
    file: UploadFile | None = File(None),
    sample: str | None = Form(None),
    source: str | None = Form(None),
    params: str | None = Form(None),
    narrative_mode: str = Form("template"),
    alpha: float = Form(DEFAULT_ALPHA),
):
    options = _options(narrative_mode, alpha)
    if mode == "upload":
        if file is None:
            raise HTTPException(400, "No file uploaded")
        data = await file.read()
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB} MB")
        name = file.filename or "upload.csv"

        def loader(log, data=data, name=name):
            log(f"Parsing {name} ({len(data) / 1024:.0f} KB)")
            return ingest.load_bytes(name, data), {"type": "upload", "name": name,
                                                   "description": f"Uploaded file {name}"}
        run_id = await start_run("upload", name, loader, options)
    elif mode == "sample":
        meta = next((s for s in _samples() if s["id"] == sample), None)
        if not meta:
            raise HTTPException(404, f"Unknown sample '{sample}'")
        path = SAMPLES_DIR / meta["file"]

        def loader(log, path=path, meta=meta):
            log(f"Reading sample dataset {meta['file']}")
            df = ingest.load_bytes(path.name, path.read_bytes())
            return df, {"type": "sample", "name": meta["name"], "description": meta["description"],
                        "url": meta.get("url")}
        run_id = await start_run("sample", meta["name"], loader, options)
    elif mode == "live":
        src = next((s for s in live.SOURCES if s["id"] == source), None)
        if not src:
            raise HTTPException(404, f"Unknown live source '{source}'")
        p = json.loads(params) if params else {}
        run_id = await start_run("live", src["name"], _live_loader(source, p), options)
    else:
        raise HTTPException(400, "mode must be upload, sample or live")
    return {"run_id": run_id}


def _live_loader(source: str, p: dict):
    def loader(log):
        df, meta = live.fetch(source, p, log)
        return ingest.finalize(df), meta
    return loader


@app.get("/api/runs")
def list_runs(limit: int = 100):
    return [_row_public(r) for r in db.list_runs(limit)]


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    row = db.get_run(run_id)
    if not row:
        raise HTTPException(404, "Run not found")
    return {"run": _row_public(row), "result": db.get_result(run_id)}


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str):
    if not db.delete_run(run_id):
        raise HTTPException(404, "Run not found")
    bus.publish("feed", {"type": "run_deleted", "run_id": run_id})
    return {"deleted": run_id}


@app.get("/api/runs/{run_id}/report.html", response_class=HTMLResponse)
def get_report(run_id: str, offline: bool = False, download: bool = False):
    if offline:
        result = db.get_result(run_id)
        if not result:
            raise HTTPException(404, "Report not found")
        html = report.render(result, offline=True)
    else:
        html = db.get_report(run_id)
        if html is None:
            raise HTTPException(404, "Report not found")
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="data-desk-report-{run_id[:8]}.html"'
    return HTMLResponse(html, headers=headers)


@app.get("/api/runs/{run_id}/result.json")
def get_result_json(run_id: str):
    result = db.get_result(run_id)
    if not result:
        raise HTTPException(404, "Result not found")
    return Response(json.dumps(result, indent=1), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="analysis-{run_id[:8]}.json"'})


# ============================================================================ metadata
@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__, "llm_available": llm_available(),
            "llm_model": ANTHROPIC_MODEL, "stages": [{"id": s, "name": n, "description": d} for s, n, d in STAGES]}


@app.get("/api/samples")
def samples():
    return _samples()


@app.get("/api/sources")
def sources():
    return live.SOURCES


@app.get("/api/stats")
def global_stats():
    return {**db.stats(), "watchers": len(watchers)}


# ============================================================================ websockets
@app.websocket("/ws/runs/{run_id}")
async def ws_run(ws: WebSocket, run_id: str):
    await ws.accept()
    channel = f"run:{run_id}"
    try:
        if bus.known(channel):
            q, history, closed = bus.subscribe(channel)
            try:
                for e in history:
                    await ws.send_text(json.dumps(e))
                if not closed:
                    while True:
                        e = await q.get()
                        if e is None:
                            break
                        await ws.send_text(json.dumps(e))
            finally:
                bus.unsubscribe(channel, q)
        else:
            row = db.get_run(run_id)
            if not row:
                await ws.send_text(json.dumps({"type": "error", "message": "Run not found"}))
            else:
                for e in db.get_events(run_id):
                    await ws.send_text(json.dumps(e))
        await ws.send_text(json.dumps({"type": "eof"}))
        await ws.close()
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/feed")
async def ws_feed(ws: WebSocket):
    await ws.accept()
    q, _, _ = bus.subscribe("feed")
    try:
        await ws.send_text(json.dumps({"type": "hello", "watchers": [_watcher_public(w) for w in watchers.values()]}))
        while True:
            getter = asyncio.create_task(q.get())
            done, _ = await asyncio.wait({getter}, timeout=25)
            if getter in done:
                e = getter.result()
                if e is None:
                    break
                await ws.send_text(json.dumps(e))
            else:
                getter.cancel()
                await ws.send_text(json.dumps({"type": "ping"}))
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        bus.unsubscribe("feed", q)


# ============================================================================ live desk watchers
watchers: dict[str, dict] = {}


class WatcherIn(BaseModel):
    source: str
    params: dict = Field(default_factory=dict)
    interval_s: int = Field(300, ge=60, le=86400)
    narrative_mode: str = "template"


def _watcher_public(w: dict) -> dict:
    return {k: v for k, v in w.items() if k != "task"}


def _diff(prev: dict | None, cur: dict | None) -> dict:
    if not cur:
        return {}
    if not prev:
        return {"first": True, "headline": cur["story"]["headline"]}
    pt = {f["title"] for f in prev["findings"]}
    ct = {f["title"] for f in cur["findings"]}
    return {
        "first": False,
        "rows_before": prev["profile"]["rows"], "rows_after": cur["profile"]["rows"],
        "headline_changed": prev["story"]["headline"] != cur["story"]["headline"],
        "headline": cur["story"]["headline"], "previous_headline": prev["story"]["headline"],
        "new_findings": sorted(ct - pt), "dropped_findings": sorted(pt - ct),
    }


async def _watch(wid: str):
    w = watchers[wid]
    src = next(s for s in live.SOURCES if s["id"] == w["source"])
    prev = None
    while True:
        w["status"] = "running"
        bus.publish("feed", {"type": "watcher", "watcher": _watcher_public(w)})
        run_id = await start_run("live", src["name"], _live_loader(w["source"], w["params"]),
                                 {"narrative_mode": w["narrative_mode"], "alpha": DEFAULT_ALPHA}, watcher_id=wid)
        w["last_run_id"] = run_id
        await _run_done[run_id]
        row = db.get_run(run_id)
        cur = db.get_result(run_id)
        w["runs"] += 1
        w["last_status"] = row["status"]
        w["last_headline"] = row.get("headline")
        w["last_error"] = row.get("error")
        w["last_diff"] = _diff(prev, cur)
        if cur:
            prev = cur
        w["status"] = "waiting"
        w["next_at"] = (datetime.now() + timedelta(seconds=w["interval_s"])).isoformat(timespec="seconds")
        bus.publish("feed", {"type": "watcher", "watcher": _watcher_public(w)})
        await asyncio.sleep(w["interval_s"])


@app.post("/api/watchers")
async def create_watcher(body: WatcherIn):
    src = next((s for s in live.SOURCES if s["id"] == body.source), None)
    if not src:
        raise HTTPException(404, "Unknown live source")
    _options(body.narrative_mode, DEFAULT_ALPHA)
    wid = uuid.uuid4().hex[:10]
    watchers[wid] = {"id": wid, "source": body.source, "source_name": src["name"], "params": body.params,
                     "interval_s": body.interval_s, "narrative_mode": body.narrative_mode,
                     "created_at": datetime.now().isoformat(timespec="seconds"), "runs": 0,
                     "status": "starting", "last_run_id": None, "next_at": None, "last_diff": None}
    watchers[wid]["task"] = asyncio.create_task(_watch(wid))
    return _watcher_public(watchers[wid])


@app.get("/api/watchers")
def list_watchers():
    return [_watcher_public(w) for w in watchers.values()]


@app.delete("/api/watchers/{wid}")
def delete_watcher(wid: str):
    w = watchers.pop(wid, None)
    if not w:
        raise HTTPException(404, "Watcher not found")
    w["task"].cancel()
    bus.publish("feed", {"type": "watcher_removed", "id": wid})
    return {"deleted": wid}


# ============================================================================ frontend (production build)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(("api/", "ws/")):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        target = FRONTEND_DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")
