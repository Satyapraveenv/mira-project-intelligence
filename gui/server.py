"""Mira GUI server. Start with: python3 gui/server.py

Binds to 127.0.0.1 only. Serves static files from gui/static/.
Imports core modules from the project root (parent of this file's directory).
Never exposes API keys to the browser. Never writes to data/.
"""
import json
import os
import pathlib
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime

ROOT = pathlib.Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

import mira_facts as mf
import mira_llm as ml
import mira_pipeline as mp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DECISIONS_PATH = str(ROOT / "decisions" / "decisions.json")
RUNS_PATH = str(ROOT / "runs" / "runs.jsonl")
TRACES_PATH = str(ROOT / "traces" / "mira_traces.jsonl")
DATA_DIR = str(ROOT / "data")
STATIC_DIR = pathlib.Path(__file__).parent / "static"

DEFAULT_AS_OF = str(mf.DEFAULT_AS_OF)
DEFAULT_START = str(mf.DEFAULT_START)


def _parse_as_of(as_of_str: str | None, use_today: bool = False) -> date:
    if use_today:
        return date.today()
    if as_of_str:
        try:
            return date.fromisoformat(as_of_str)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid as_of date: {as_of_str}")
    return mf.DEFAULT_AS_OF


def _make_llm(model: str):
    if model == "mock":
        return ml.MockLLM()
    if model == "gpt-4o-mini":
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise HTTPException(status_code=400, detail="OPENAI_API_KEY not set")
        return ml.OpenAILLM("gpt-4o-mini")
    raise HTTPException(status_code=422, detail=f"Unknown model: {model}")


def _pack_with_decisions(as_of: date) -> dict:
    pack = mf.facts_pack(DATA_DIR, as_of, mf.DEFAULT_START)
    decisions = mp.load_decisions(DECISIONS_PATH)
    mf.apply_decisions(pack, decisions)
    return pack


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)


# ---------- config ----------

@app.get("/api/config")
def api_config():
    langfuse_host = os.environ.get("LANGFUSE_HOST", "")
    return {
        "default_as_of": DEFAULT_AS_OF,
        "default_start": DEFAULT_START,
        "models": ["mock", "gpt-4o-mini"],
        "has_openai_key": bool(os.environ.get("OPENAI_API_KEY", "")),
        "has_langfuse": bool(
            os.environ.get("LANGFUSE_SECRET_KEY", "") and
            os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        ),
        "langfuse_host": langfuse_host,
    }


# ---------- ask ----------

class AskRequest(BaseModel):
    request: str
    audience: str | None = None
    as_of: str | None = None
    use_today: bool = False
    model: str = "mock"


@app.post("/api/ask")
def api_ask(body: AskRequest):
    if not body.request.strip():
        raise HTTPException(status_code=422, detail="request must not be empty")
    audience = body.audience if body.audience in mp.AUDIENCES else None
    as_of = _parse_as_of(body.as_of, body.use_today)
    llm = _make_llm(body.model)
    result = mp.run(
        body.request, llm,
        data_dir=DATA_DIR,
        as_of=as_of,
        decisions_path=DECISIONS_PATH,
        trace_path=TRACES_PATH,
        runs_path=RUNS_PATH,
        audience=audience,
    )
    # When held, enrich the conflict ID list with full conflict objects so the
    # frontend can show raw evidence without a second round trip.
    if result.get("status") == "held" and result.get("conflicts"):
        conflict_ids = set(result["conflicts"])
        pack = _pack_with_decisions(as_of)
        full = [
            {"id": c["id"], "type": c["type"], "evidence": c["evidence"],
             "affects": c["affects"], "fingerprint": c["fingerprint"],
             "status": c.get("status", "open")}
            for c in pack["conflicts"] if c["id"] in conflict_ids
        ]
        result = dict(result)
        result["conflicts"] = full
    return result


# ---------- dashboard ----------

@app.get("/api/dashboard")
def api_dashboard(as_of: str | None = None, use_today: bool = False):
    d = _parse_as_of(as_of, use_today)
    pack = _pack_with_decisions(d)
    open_conflicts = [c for c in pack["conflicts"] if c.get("status", "open") != "resolved"]
    workload = [
        {"person": person, **stats}
        for person, stats in pack["workload"].items()
    ]
    tasks_with_due = {t["id"]: t.get("due") for t in pack["tasks"]}
    at_risk_detail = []
    for item in pack["at_risk"]:
        t_id = item["id"]
        at_risk_detail.append({
            "id": t_id,
            "reasons": item.get("reasons", []),
            "due": str(tasks_with_due.get(t_id, "")) if tasks_with_due.get(t_id) else None,
        })
    blocked_detail = []
    for t_id in pack["blocked"]:
        task = next((t for t in pack["tasks"] if t["id"] == t_id), None)
        if task:
            blocked_detail.append({
                "id": t_id,
                "name": task["name"],
                "due": str(task["due"]) if task.get("due") else None,
                "assignee": task.get("assignee"),
            })
    return {
        "as_of": str(d),
        "health": pack["health"],
        "counts": pack["counts"],
        "at_risk": at_risk_detail,
        "blocked": blocked_detail,
        "upcoming_milestones": pack["upcoming_milestones"],
        "open_conflicts_count": len(open_conflicts),
        "held_outputs": mf.held_outputs(pack),
        "workload": workload,
        "freshness_line": pack["freshness_line"],
        "assumptions": pack["assumptions"],
    }


# ---------- conflicts ----------

@app.get("/api/conflicts")
def api_conflicts(as_of: str | None = None, use_today: bool = False):
    d = _parse_as_of(as_of, use_today)
    pack = _pack_with_decisions(d)
    held = mf.held_outputs(pack)
    conflicts = []
    for c in pack["conflicts"]:
        created = c.get("id", "")
        age_days = None
        conflicts.append({
            "id": c["id"],
            "type": c["type"],
            "evidence": c["evidence"],
            "affects": c["affects"],
            "fingerprint": c["fingerprint"],
            "status": c.get("status", "open"),
            "note": c.get("note"),
            "decision": c.get("decision"),
        })
    return {
        "as_of": str(d),
        "conflicts": conflicts,
        "held_outputs": held,
    }


# ---------- sign ----------

class SignRequest(BaseModel):
    outcome: str
    decided_by: str
    rationale: str


@app.post("/api/conflicts/{conflict_id}/sign")
def api_sign(conflict_id: str, body: SignRequest):
    if not body.decided_by.strip():
        raise HTTPException(status_code=422, detail="decided_by must not be empty")
    if not body.rationale.strip():
        raise HTTPException(status_code=422, detail="rationale must not be empty")
    if body.outcome not in mp.OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {sorted(mp.OUTCOMES)}")
    pack = mf.facts_pack(DATA_DIR, mf.DEFAULT_AS_OF, mf.DEFAULT_START)
    conflict = next((c for c in pack["conflicts"] if c["id"] == conflict_id), None)
    if conflict is None:
        raise HTTPException(status_code=404, detail=f"Conflict {conflict_id!r} not found")
    decision = mp.sign_decision(
        DECISIONS_PATH, conflict,
        body.outcome, body.decided_by.strip(), body.rationale.strip(),
    )
    return {"ok": True, "decision": decision}


# ---------- runs ----------

@app.get("/api/runs")
def api_runs(limit: int = 50):
    try:
        with open(RUNS_PATH, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return {"runs": []}
    records = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
        if len(records) >= limit:
            break
    return {"runs": records}


# ---------- traces ----------

@app.get("/api/traces/{trace_id}")
def api_traces(trace_id: str):
    spans = []
    try:
        with open(TRACES_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    s = json.loads(line)
                except ValueError:
                    continue
                if s.get("trace_id") == trace_id:
                    spans.append(s)
    except OSError:
        pass
    return {"trace_id": trace_id, "spans": spans}


# ---------- static files and SPA root ----------

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/{path:path}")
def serve_fallback(path: str):
    candidate = STATIC_DIR / path
    if candidate.exists() and candidate.is_file():
        return FileResponse(str(candidate))
    return FileResponse(str(STATIC_DIR / "index.html"))


# ---------- entry point ----------

if __name__ == "__main__":
    import webbrowser
    import uvicorn

    print(f"Mira GUI starting. Project root: {ROOT}")
    print("Open: http://127.0.0.1:7860")
    webbrowser.open("http://127.0.0.1:7860")
    uvicorn.run(app, host="127.0.0.1", port=7860, log_level="warning")
