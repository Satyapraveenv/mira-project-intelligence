"""Mira pipeline: Router, Data Checker, gates, specialist, Grounding Verifier, Audience Writer.

The pipeline is a chain of stage functions that pass one JSON-safe state dict along. run() chains them
in-process; the Langflow detailed flow wires the same stage functions as separate nodes.

Flow: request -> Router (LLM) -> facts pack (code) -> sufficiency gate (code) -> conflict gate
(human decisions) -> specialist (LLM) -> Grounding Verifier (code, one retry) -> Audience
Writer (LLM, subset-checked) -> Markdown render (code) -> run record.
Nothing unverified is ever returned, and nothing is sent or written back to the project files.
"""
import hashlib
import json
import os
import re
import uuid
from collections import Counter
from datetime import date, datetime

import mira_facts as mf
import mira_prompts as P
import mira_render as R
from mira_llm import cost_usd
from mira_trace import Tracer
from mira_verify import _texts as verify_texts, subset_check, tokens, verify

OUTPUT_KEY = {"plan": "plan", "risk": "risk", "status": "status", "update": "status",
              "milestones": "milestones", "tracking": "tracking", "resource": "resource"}
VALID_TYPES = set(OUTPUT_KEY) | {"out_of_scope", "unclear"}
GATE_TYPE = {"tracking": "status", "resource": "status"}
AUDIENCES = {"engineering", "business", "leadership", "client"}
OUTCOMES = {"data_correct", "typo", "more_data_needed", "provisional"}


# ---------- decisions (human sign-off log) ----------
def load_decisions(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def sign_decision(path, conflict, outcome, decided_by, rationale):
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(OUTCOMES)}")
    d = mf.new_decision(conflict, outcome, decided_by, rationale)
    ds = [x for x in load_decisions(path) if x["conflict_id"] != conflict["id"]] + [d]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ds, f, indent=1)
    return d


# ---------- scoping: only the facts a request needs ----------
def _open_for(conflicts, key, task_ids=None):
    out = []
    for c in conflicts:
        if key not in c["affects"]:
            continue
        t = c["evidence"].get("task")
        if task_ids is not None and t is not None and t not in task_ids:
            continue
        out.append(c)
    return out


def scope_for(rtype, pack, sprint=None, top_n=None):
    tasks = pack["tasks"] if not sprint else [t for t in pack["tasks"] if t["sprint"] == sprint]
    ids = {t["id"] for t in tasks}
    cnt = Counter(t["status"] for t in tasks)
    counts = {s: cnt.get(s, 0) for s in mf.STATUSES}
    counts["total"] = len(tasks)
    base = {"as_of": pack["as_of"], "project_start": pack["project_start"],
            "freshness_line": pack["freshness_line"]}
    if rtype == "plan":
        return {**base, "phases": pack["phases"], "milestones": pack["milestones"], "goals": pack["goals"],
                "description": pack["description"], "conflicts": _open_for(pack["conflicts"], "plan")}
    if rtype == "risk":
        return {**base, "risks": pack["risks"], "top_n": top_n,
                "tasks": [{k: t[k] for k in ("id", "name", "status", "label", "due")} for t in pack["tasks"]],
                "blocked": pack["blocked"], "phases": pack["phases"], "conflicts": []}
    if rtype in ("milestones", "tracking"):
        return {**base, "phases": pack["phases"], "milestones": pack["milestones"],
                "upcoming_milestones": pack["upcoming_milestones"], "tasks": pack["tasks"],
                "at_risk": pack["at_risk"], "health": pack["health"],
                "conflicts": _open_for(pack["conflicts"], "milestones")}
    # status and update
    return {**base, "sprint": sprint, "counts": counts, "tasks": tasks,
            "blocked": [t["id"] for t in tasks if t["status"] == "Blocked"],
            "at_risk": [r for r in pack["at_risk"] if r["id"] in ids],
            "overdue": [i for i in pack["overdue"] if i in ids],
            "health": mf.compute_health(tasks, pack["as_of"]),
            "upcoming_milestones": pack["upcoming_milestones"],
            "conflicts": _open_for(pack["conflicts"], "status", ids)}


# ---------- helpers ----------
def _parse(text):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    try:
        return json.loads(t)
    except ValueError:
        return None


class Usage:
    def __init__(self, model):
        self.model, self.p, self.c = model, 0, 0

    def add(self, u):
        self.p += (u or {}).get("prompt_tokens", 0)
        self.c += (u or {}).get("completion_tokens", 0)

    def dict(self):
        u = {"prompt_tokens": self.p, "completion_tokens": self.c}
        return {**u, "cost_usd": round(cost_usd(self.model, u), 6)}


INLINE_HINT = re.compile(r"['\"\u2018\u201c]\w|\b(?:no|without)\b[^.]{0,40}\b(?:details|data|information|notes|board|description)\b", re.I)


NAMES_PROJECT = re.compile(r"ABCDE|\bboard\b|\bsprint\b|\btask\b|\bcopy\b", re.I)


def _supplies_own_input(request):
    """True when the user pasted their own description or said they have no project data."""
    return bool(INLINE_HINT.search(request)) or len(request.split()) >= 25


def _ranked_risk_ids(out):
    seen = []
    for it in out.get("items", []):
        for r in it.get("refs", []):
            if re.fullmatch(r"R\d{2}", r) and r not in seen:
                seen.append(r)
                break
    return seen


def _result(status, md, **kw):
    return {"status": status, "markdown": md, **kw}


# ---------- state and stages ----------
SPECIALIST_FOR = {"plan": "plan", "risk": "risk", "status": "status", "update": "status",
                  "milestones": "milestones", "tracking": "milestones"}


def new_state(request, as_of=mf.DEFAULT_AS_OF, start=mf.DEFAULT_START, audience=None, model="mock",
              data_dir="data", decisions_path="decisions/decisions.json", stated_counts=None,
              board_export_date=None, tasks_override=None, trace_id=None):
    return {"request": request, "as_of": str(as_of), "start": str(start), "audience": audience, "model": model,
            "data_dir": data_dir, "decisions_path": decisions_path, "stated_counts": stated_counts,
            "board_export_date": str(board_export_date) if board_export_date else None,
            "tasks_override": tasks_override, "trace_id": trace_id or uuid.uuid4().hex,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0}, "route": None, "pack": None, "scope": None,
            "draft": None, "payload": None, "system": None, "role": None, "out": None, "final": None,
            "aud_used": None, "audience_note": "", "result": None}


def _add_usage(state, u):
    state["usage"]["prompt_tokens"] += (u or {}).get("prompt_tokens", 0)
    state["usage"]["completion_tokens"] += (u or {}).get("completion_tokens", 0)


def usage_dict(state):
    return {**state["usage"], "cost_usd": round(cost_usd(state["model"], state["usage"]), 6)}


def stage_router(state, llm, tr, prompt=None):
    """Router agent (LLM): classify the request. Ends the run early for out-of-scope or unclear requests."""
    request = state["request"]
    with tr.span("router", {"request": request}) as s:
        txt, u = llm.complete("router", prompt or P.ROUTER, {"request": request})
        _add_usage(state, u)
        r = _parse(txt) or {}
        rtype = r.get("type") if r.get("type") in VALID_TYPES else "unclear"
        target = r.get("target") if r.get("target") in ("project", "inline") else "project"
        if target == "inline" and not _supplies_own_input(request):
            target = "project"  # default to the loaded project unless the user clearly supplied their own input
        elif target == "project" and INLINE_HINT.search(request) and not NAMES_PROJECT.search(request):
            target = "inline"  # the user quoted their own text or said they have no details, so do not use the loaded project
        aud = (state["audience"] or r.get("audience") or None)
        aud = aud if aud in AUDIENCES else None
        sprint = r.get("sprint") if isinstance(r.get("sprint"), str) else None
        top_n = r.get("top_n") if isinstance(r.get("top_n"), int) and r["top_n"] > 0 else None
        route = {"type": rtype, "target": target, "sprint": sprint, "audience": aud, "top_n": top_n,
                 "scope_reason": r.get("scope_reason")}
        s["output"] = route
    state["route"] = route
    if rtype == "out_of_scope":
        state["result"] = _result("declined", R.render_declined(route["scope_reason"]), router=route)
    elif rtype == "unclear":
        state["result"] = _result("unclear", "# Request not understood\n\nMira could not tell whether you want a plan, "
                                  "risks, status, milestones, tracking, a stakeholder update or a workload view. "
                                  "Please rephrase.", router=route)
    return state


def stage_data(state, tr):
    """Data Checker (code): facts pack, conflict detection, signed decisions applied."""
    if state["result"] is not None:
        return state
    as_of, start = date.fromisoformat(state["as_of"]), date.fromisoformat(state["start"])
    with tr.span("data_checker", {"as_of": state["as_of"], "data_dir": state["data_dir"]}) as s:
        pack = mf.facts_pack(state["data_dir"], as_of=as_of, start=start, stated_counts=state["stated_counts"],
                             board_export_date=state["board_export_date"], tasks_override=state["tasks_override"])
        pack = mf.apply_decisions(pack, load_decisions(state["decisions_path"]))
        s["output"] = {"counts": pack["counts"], "conflicts": [(c["id"], c["status"]) for c in pack["conflicts"]],
                       "health": pack["health"]["level"]}
    state["pack"] = pack
    return state


def stage_gates(state, tr):
    """Gates (code): enough source data? Any unsigned conflict on this output? Workload view is code-only."""
    if state["result"] is not None:
        return state
    route, pack = state["route"], state["pack"]
    rtype, target = route["type"], route["target"]
    sources = set(pack["sources_present"]) if target == "project" else set()
    ok, missing, ask = mf.sufficiency(GATE_TYPE.get(rtype, rtype), sources)
    with tr.span("sufficiency_gate", {"type": rtype, "target": target}) as s:
        s["output"] = {"ok": ok, "missing": missing}
    if not ok:
        state["result"] = _result("insufficient", R.render_insufficient(rtype, ask), router=route, missing=missing)
        return state
    key = OUTPUT_KEY[rtype]
    held = mf.held_outputs(pack)
    with tr.span("conflict_gate", {"output": key}) as s:
        s["output"] = {"held_outputs": held}
    if key in held:
        cs = [c for c in pack["conflicts"] if key in c["affects"] and c.get("status", "open") != "resolved"]
        state["result"] = _result("held", R.render_held(rtype, cs), router=route, conflicts=[c["id"] for c in cs])
    elif rtype == "resource":
        state["result"] = _result("ok", R.render_resource(pack), router=route, verified=True)
    return state


def stage_specialist(state, llm, tr, which, prompt=None):
    """Specialist agent (LLM). Acts only when the router chose it; otherwise passes the state through."""
    if state["result"] is not None or state["draft"] is not None:
        return state
    route = state["route"]
    rtype = route["type"]
    if SPECIALIST_FOR.get(rtype) != which:
        return state
    scope = scope_for(rtype, state["pack"], route["sprint"], route["top_n"])
    role = {"update": "status", "tracking": "tracking"}.get(rtype, rtype)
    # allowed_refs lists every ref the Grounding Verifier will accept, so the model has no reason to guess
    from mira_verify import universe
    payload = {"request": state["request"], "facts": scope, "top_n": route["top_n"],
               "allowed_refs": sorted(universe(scope)["refs"])}
    system = prompt or P.SPECIALISTS[rtype]
    with tr.span(f"specialist_{rtype}_try1", {"payload_keys": list(payload)}) as s:
        txt, u = llm.complete(role, system, payload)
        _add_usage(state, u)
        s["output"] = {"chars": len(txt or "")}
    state.update(scope=scope, payload=payload, system=system, role=role, draft=txt)
    return state


def stage_verify(state, llm, tr):
    """Grounding Verifier (code): every ref, ID, date and number must exist in the facts. One retry."""
    if state["result"] is not None or state["draft"] is None:
        return state
    rtype, top_n, scope = state["route"]["type"], state["route"]["top_n"], state["scope"]
    txt, payload, problems, out = state["draft"], state["payload"], [], None
    for attempt in (1, 2):
        if attempt == 2:
            payload = {**payload, "feedback": "Your last reply was rejected. Fix these problems: " + "; ".join(problems)}
            with tr.span(f"specialist_{rtype}_try2", {"payload_keys": list(payload)}) as s:
                txt, u = llm.complete(state["role"], state["system"], payload)
                _add_usage(state, u)
                s["output"] = {"chars": len(txt or "")}
        with tr.span(f"grounding_verifier_try{attempt}", {"type": rtype}) as s:
            out = _parse(txt)
            if out is None:
                good, problems = False, ["output was not valid JSON"]
            else:
                good, problems = verify(out, scope)
                if good and rtype == "risk":
                    ids = _ranked_risk_ids(out)
                    if top_n and len(ids) != top_n:
                        good, problems = False, [f"expected exactly {top_n} ranked risks, got {len(ids)}"]
            s["output"] = {"verified": good, "problems": problems}
        if good:
            if not (rtype == "risk" and top_n):
                out["criteria"] = ""  # ranking criteria only make sense when a ranking was requested
            state["out"] = out
            return state
    state["result"] = _result("verification_failed",
                              "# Draft rejected\n\nMira's draft failed the grounding check twice, so nothing was released:\n\n"
                              + "\n".join(f"- {p}" for p in problems), router=state["route"], problems=problems)
    return state


def stage_audience(state, llm, tr, prompt=None):
    """Audience Writer (LLM): rewrite for a stakeholder group. May omit facts, never add; falls back to the base."""
    if state["result"] is not None or state["out"] is None:
        return state
    route, out, scope = state["route"], state["out"], state["scope"]
    aud = route["audience"]
    state["final"], state["aud_used"] = out, aud
    if aud and route["type"] in ("status", "update"):
        payload = {"base": out, "audience": aud, "facts": scope}
        good, probs = False, []
        for attempt in (1, 2):
            with tr.span("audience_writer" if attempt == 1 else "audience_writer_try2", {"audience": aud}) as s:
                txt, u = llm.complete("audience", prompt or P.AUDIENCE, payload)
                _add_usage(state, u)
                a_out = _parse(txt)
                if a_out is None:
                    good, probs = False, ["audience output was not valid JSON"]
                else:
                    good, probs = verify(a_out, scope)
                    if good:
                        good, probs = subset_check(out, a_out)
                    if good and aud == "client":
                        leaked = sorted({i for _, t in verify_texts(a_out) for i in tokens(t)[0]})
                        if leaked:
                            good, probs = False, [f"client version must not contain internal IDs: {', '.join(leaked)}"]
                s["output"] = {"verified": good, "problems": probs}
            if good:
                state["final"] = a_out
                break
            payload = {**payload, "feedback": "Your last reply was rejected. Fix these problems: " + "; ".join(probs)}
        if not good:
            why = "contained internal IDs" if aud == "client" and any("internal IDs" in x for x in probs) else "failed verification"
            state["audience_note"] = f"\n\n_The {aud} version {why}, so the base version is shown for you to edit._"
            state["aud_used"] = None
    return state


def stage_render(state, tr=None):
    """Renderer (code): all numbers, IDs, dates and tables are written here, never by the model."""
    if state["result"] is not None or state["final"] is None:
        return state
    route, scope, final, aud = state["route"], state["scope"], state["final"], state["aud_used"]
    rtype, sprint, top_n = route["type"], route["sprint"], route["top_n"]
    if rtype == "plan":
        md = R.render_plan(scope, final)
    elif rtype == "risk":
        md = R.render_risk(scope, final, _ranked_risk_ids(final) if top_n else None)
    elif rtype == "milestones":
        md = R.render_milestones(scope, final)
    elif rtype == "tracking":
        md = R.render_milestones(scope, final, tracking=True)
    elif rtype == "update" or (rtype == "status" and aud == "client"):
        md = R.render_update(scope, final, aud, sprint)  # the client view never lists internal IDs or assignees
    else:
        title = f"{sprint} status report" if sprint else "Weekly status report"
        md = R.render_status(scope, final, title, aud)
    state["result"] = _result("ok", md + state["audience_note"], router=route, verified=True, output=final)
    return state


def record_run(state, runs_path):
    """Append one run record (no report text, only a hash) to the runs log."""
    res = state["result"] or {}
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "trace_id": state["trace_id"],
           "request": state["request"], "as_of": state["as_of"], "audience": state["audience"],
           "model": state["model"], "status": res.get("status", "error"), "router": res.get("router"),
           "usage": usage_dict(state),
           "output_sha": hashlib.sha256((res.get("markdown") or "").encode()).hexdigest()[:12]}
    try:
        os.makedirs(os.path.dirname(runs_path) or ".", exist_ok=True)
        with open(runs_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except OSError:
        pass


# ---------- main entry (in-process chain of the stages) ----------
def run(request, llm, data_dir="data", as_of=mf.DEFAULT_AS_OF, start=mf.DEFAULT_START, audience=None,
        decisions_path="decisions/decisions.json", trace_path="traces/mira_traces.jsonl",
        runs_path="runs/runs.jsonl", stated_counts=None, board_export_date=None, tasks_override=None,
        langfuse=True):
    tr = Tracer(trace_path, langfuse)
    state = new_state(request, as_of, start, audience, llm.model, data_dir, decisions_path, stated_counts,
                      board_export_date, tasks_override, trace_id=tr.trace_id)
    try:
        stage_router(state, llm, tr)
        stage_data(state, tr)
        stage_gates(state, tr)
        for which in ("plan", "risk", "status", "milestones"):
            stage_specialist(state, llm, tr, which)
        stage_verify(state, llm, tr)
        stage_audience(state, llm, tr)
        stage_render(state, tr)
    finally:
        record_run(state, runs_path)
        tr.flush()
    res = state["result"]
    res["trace_id"], res["usage"] = tr.trace_id, usage_dict(state)
    return res
