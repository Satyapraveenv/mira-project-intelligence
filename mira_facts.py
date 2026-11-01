"""Mira Data Checker and facts pack (plain code, no LLM).

Everything an LLM agent is allowed to state about the project is computed here:
counts, dates, statuses, phase links, conflicts, workload, and the sufficiency
check. The LLM agents receive the JSON this module returns and may only reference it.

Design rules (from the Mira plan):
- Raw files are read only. Nothing here edits them.
- Conflicts are detected and listed, never resolved. A human signs a decision.
- A signed decision is tied to a hash of the conflict evidence, so it expires
  automatically when the underlying data changes.
"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

DEFAULT_START = date(2026, 3, 30)     # Assumption 1 (inferred from due dates)
DEFAULT_AS_OF = date(2026, 4, 20)     # Assumption 2 (demo default, settable)
AT_RISK_DAYS = 7                      # Rule 1, inclusive, configurable
MILESTONE_WINDOW_DAYS = 14            # "next 2 weeks"

# Assumption 10: label implied phase. None means the label spans phases and
# needs an explicit human mapping.
LABEL_PHASE = {
    "Planning": 1, "Analysis": 2, "Use Cases": 3, "Data Prep": 4, "Model Dev": 4,
    "Pilot": 5, "Evaluation": 6, "Deployment": 7, "Monitoring": 8,
    "Security": None, "Compliance": None,
}

STATUSES = ["Done", "In Progress", "Blocked", "To Do"]

# Which outputs a conflict type puts on hold until a human signs a decision.
AFFECTS = {
    "label_vs_due_date_phase": ["milestones", "readiness"],
    "board_end_vs_timeline": ["milestones"],
    "stated_count_vs_board": ["status"],
    "as_of_out_of_range": ["status", "milestones"],
}


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _d(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def _hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def load(data_dir):
    tl = _read(f"{data_dir}/project_timeline.csv")
    rk = _read(f"{data_dir}/project_risks.csv")
    tb = _read(f"{data_dir}/sample_task_board.csv")
    return tl, rk, tb


def week_of(day, start):
    return (day - start).days // 7 + 1


def phase_for_week(week, phases):
    for p in phases:
        if p["start_week"] <= week <= p["end_week"]:
            return p["phase"]
    return None


def build_phases(tl, start):
    phases, milestones = [], []
    for r in tl:
        sw, ew = int(r["start_week"]), int(r["end_week"])
        ph = {
            "phase": int(r["phase"]), "name": r["phase_name"],
            "start_week": sw, "end_week": ew,
            "start_date": start + timedelta(days=7 * (sw - 1)),
            "end_date": start + timedelta(days=7 * ew - 1),
        }
        phases.append(ph)
        for m in [x.strip() for x in r["milestones_deliverables"].split(";") if x.strip()]:
            milestones.append({"phase": ph["phase"], "name": m, "due": ph["end_date"]})
    return phases, milestones


def _days(n):
    return f"{n} day" + ("" if n == 1 else "s")


def compute_health(tasks, as_of):
    """Rule-based health (code, not LLM). Red: any overdue task that is not Done, or a
    Blocked task due within the at-risk window. Amber: any Blocked task or any task due
    within the window. Green otherwise. The rule is a proposal and is configurable."""
    reasons, red = [], False
    for t in tasks:
        if t["status"] == "Done":
            continue
        d = t["days_to_due"]
        if d < 0:
            red = True
            reasons.append(f"{t['id']} overdue")
        elif t["status"] == "Blocked" and d <= AT_RISK_DAYS:
            red = True
            reasons.append(f"{t['id']} blocked and due in {_days(d)}")
        elif t["status"] == "Blocked":
            reasons.append(f"{t['id']} blocked")
        elif d <= AT_RISK_DAYS:
            reasons.append(f"{t['id']} due in {_days(d)}")
    level = "Red" if red else ("Amber" if reasons else "Green")
    return {"level": level, "reasons": reasons}


def extract_goals(text):
    """Goals sentence taken verbatim from the description (first sentence starting with 'Key goals')."""
    if not text:
        return []
    for sent in text.replace("\n", " ").split(". "):
        if sent.strip().startswith("Key goals"):
            return [sent.strip().rstrip(".") + "."]
    return []



def facts_pack(data_dir, as_of=DEFAULT_AS_OF, start=DEFAULT_START, stated_counts=None,
               board_export_date=None, tasks_override=None):
    tl, rk, tb = load(data_dir)
    if tasks_override is not None:
        tb = tasks_override
    desc_path = f"{data_dir}/project_description.txt"
    try:
        with open(desc_path, encoding="utf-8") as f:
            description = f.read().strip()
    except OSError:
        description = None
    sources_present = {"timeline", "risks", "tasks"} | ({"description"} if description else set())
    phases, milestones = build_phases(tl, start)
    tasks = []
    for r in tb:
        due = _d(r["due_date"])
        wk = week_of(due, start)
        tasks.append({
            "id": r["task_id"], "name": r["task_name"], "status": r["status"],
            "assignee": r["assignee"], "priority": r["priority"], "sprint": r["sprint"],
            "due": due, "label": r["labels"], "description": r["description"],
            "days_to_due": (due - as_of).days, "due_week": wk,
            "phase_by_date": phase_for_week(wk, phases),
            "phase_by_label": LABEL_PHASE.get(r["labels"]),
        })

    counts = Counter(t["status"] for t in tasks)
    counts_out = {s: counts.get(s, 0) for s in STATUSES}
    counts_out["total"] = len(tasks)

    by_sprint = defaultdict(list)
    for t in tasks:
        by_sprint[t["sprint"]].append(t["id"])

    not_done = [t for t in tasks if t["status"] != "Done"]
    overdue = [t["id"] for t in not_done if t["days_to_due"] < 0]
    at_risk = []
    for t in tasks:
        reasons = []
        if t["status"] == "Blocked":
            reasons.append("blocked")
        if t["status"] != "Done" and t["days_to_due"] < 0:
            reasons.append("overdue")
        elif t["status"] != "Done" and t["days_to_due"] <= AT_RISK_DAYS:
            reasons.append(f"due in {_days(t['days_to_due'])}")
        if reasons:
            at_risk.append({"id": t["id"], "reasons": reasons})

    workload = defaultdict(lambda: {"total": 0, "open": 0, "by_status": Counter()})
    for t in tasks:
        w = workload[t["assignee"]]
        w["total"] += 1
        w["by_status"][t["status"]] += 1
        if t["status"] != "Done":
            w["open"] += 1
    workload_out = {k: {"total": v["total"], "open": v["open"], "by_status": dict(v["by_status"])}
                    for k, v in sorted(workload.items())}

    horizon = as_of + timedelta(days=MILESTONE_WINDOW_DAYS)
    upcoming = [m for m in milestones if as_of <= m["due"] <= horizon]

    # ---- conflicts (detected, never resolved) ----
    conflicts = []
    for t in tasks:
        pl, pd_ = t["phase_by_label"], t["phase_by_date"]
        if pl is not None and pd_ != pl:
            ev = {"task": t["id"], "label": t["label"], "label_phase": pl,
                  "due": str(t["due"]), "due_week": t["due_week"], "date_phase": pd_}
            conflicts.append({"id": f"C-PHASE-{t['id']}", "type": "label_vs_due_date_phase",
                              "evidence": ev})
    last_week = max(t["due_week"] for t in tasks)
    tl_end = max(p["end_week"] for p in phases)
    if last_week != tl_end:
        conflicts.append({"id": "C-BOARD-END", "type": "board_end_vs_timeline",
                          "evidence": {"board_last_due_week": last_week,
                                       "timeline_end_week": tl_end}})
    if stated_counts:
        for status, stated in stated_counts.items():
            actual = counts_out.get(status, 0)
            if stated != actual:
                conflicts.append({"id": f"C-COUNT-{status.replace(' ', '')}",
                                  "type": "stated_count_vs_board",
                                  "evidence": {"status": status, "stated": stated,
                                               "board": actual}})
    all_due = [t["due"] for t in tasks]
    if as_of < start or as_of > max(all_due):
        conflicts.append({"id": "C-ASOF", "type": "as_of_out_of_range",
                          "evidence": {"as_of": str(as_of), "project_start": str(start),
                                       "last_task_due": str(max(all_due))}})
    for c in conflicts:
        c["fingerprint"] = _hash(c["evidence"])
        c["affects"] = AFFECTS[c["type"]]

    needs_mapping = [{"task": t["id"], "label": t["label"], "date_phase": t["phase_by_date"]}
                     for t in tasks if t["phase_by_label"] is None]

    stale = {
        "overdue_not_done": overdue,
        "in_progress_past_due": [t["id"] for t in tasks
                                 if t["status"] == "In Progress" and t["days_to_due"] < 0],
    }

    return {
        "as_of": str(as_of), "project_start": str(start),
        "board_export_date": str(board_export_date) if board_export_date else None,
        "freshness_line": f"Data as of {as_of}" + (f", board exported {board_export_date}"
                                                    if board_export_date else ", board export date not supplied"),
        "counts": counts_out,
        "by_sprint": dict(by_sprint),
        "overdue": overdue, "at_risk": at_risk, "blocked": [t["id"] for t in tasks if t["status"] == "Blocked"],
        "workload": workload_out,
        "phases": [{**p, "start_date": str(p["start_date"]), "end_date": str(p["end_date"])} for p in phases],
        "milestones": [{**m, "due": str(m["due"])} for m in milestones],
        "upcoming_milestones": [{**m, "due": str(m["due"])} for m in upcoming],
        "tasks": [{**t, "due": str(t["due"])} for t in tasks],
        "risks": rk,
        "conflicts": conflicts,
        "needs_explicit_mapping": needs_mapping,
        "stale_signs": stale,
        "description": description, "goals": extract_goals(description),
        "sources_present": sorted(sources_present),
        "health": compute_health(tasks, as_of),
        "assumptions": ["A1 start date " + str(start), "A2 as-of date " + str(as_of),
                        "A10 label to phase mapping inferred, phase assigned by due-date window"],
    }


def apply_decisions(pack, decisions):
    """Mark each conflict open or resolved. A decision counts only while its
    stored fingerprint still matches the conflict evidence (expiry rule)."""
    by_id = {d["conflict_id"]: d for d in decisions}
    for c in pack["conflicts"]:
        d = by_id.get(c["id"])
        if d is None:
            c["status"] = "open"
        elif d.get("fingerprint") == c["fingerprint"]:
            c["decision"] = {k: d.get(k) for k in ("outcome", "decided_by", "date", "rationale")}
            c["status"] = "awaiting_data" if d.get("outcome") == "more_data_needed" else "resolved"
        else:
            c["status"] = "open"
            c["note"] = "decision expired: data changed since it was signed"
    return pack


def held_outputs(pack):
    held = set()
    for c in pack["conflicts"]:
        if c.get("status", "open") != "resolved":
            held.update(c["affects"])
    return sorted(held)


REQUIREMENTS = {
    "plan": ["description", "timeline"],
    "risk": ["description", "risks"],
    "status": ["tasks"],
    "milestones": ["timeline", "tasks"],
    "update": ["tasks"],
}
ASKS = {
    "plan": ["scope", "goals and deliverables", "timeline", "team size"],
    "risk": ["project details (scope, domain, timeline)"],
    "status": ["a task board export with statuses, assignees and due dates"],
    "milestones": ["a timeline and task board"],
    "update": ["a task board export for the sprint"],
}


def sufficiency(request_type, sources_present):
    """Deterministic gate. sources_present is a set from
    {'description','timeline','risks','tasks'}. Returns (ok, missing, ask)."""
    need = REQUIREMENTS.get(request_type, [])
    missing = [n for n in need if n not in sources_present]
    if missing:
        return False, missing, ASKS.get(request_type, [])
    return True, [], []


def new_decision(conflict, outcome, decided_by, rationale, day=None):
    return {"conflict_id": conflict["id"], "outcome": outcome, "decided_by": decided_by,
            "date": str(day or date.today()), "rationale": rationale,
            "fingerprint": conflict["fingerprint"]}


if __name__ == "__main__":
    import sys
    p = facts_pack(sys.argv[1] if len(sys.argv) > 1 else "data")
    print(json.dumps({k: p[k] for k in ("freshness_line", "counts", "blocked", "at_risk",
                                       "upcoming_milestones")}, indent=1))
    print(len(p["conflicts"]), "conflicts")
