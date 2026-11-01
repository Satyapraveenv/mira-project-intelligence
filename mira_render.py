"""Renderers: turn verified facts plus the verified agent JSON into Markdown.

Everything factual (counts, task lists, dates, register text, phase tables, health) is
written here by code. The agent JSON only supplies short narrative sentences with refs.
"""

STATUSES = ["Done", "In Progress", "Blocked", "To Do"]
FOOT = "\n\n---\nDraft prepared by Mira. Not shared. Pending PM/TPM review and approval."


def _narr(out, refs=True):
    if not out:
        return ""
    def line(c):
        r = f" [{', '.join(c['refs'])}]" if refs else ""
        return f"{c['text']}{r}"
    parts = [line(out["summary"])]
    if out.get("criteria"):
        parts.append(f"\nRanking criteria (proposal): {out['criteria']}")
    if out.get("items"):
        parts.append("\n" + "\n".join(f"- {line(i)}" for i in out["items"]))
    if out.get("actions"):
        parts.append("\nSuggested actions (not decided):\n" + "\n".join(f"- {line(a)}" for a in out["actions"]))
    return "\n".join(parts)


def _conflict_note(scope):
    cs = scope.get("conflicts", [])
    open_c = [c for c in cs if c.get("status", "open") != "resolved"]
    prov = [c for c in cs if c.get("status") == "resolved" and (c.get("decision") or {}).get("outcome") == "provisional"]
    note = ""
    if open_c:
        note += "\n\n**Open data conflicts (provisional until a PM/TPM signs a decision):** " + \
            ", ".join(c["id"] for c in open_c)
    if prov:
        note += "\n\n**Signed as provisional:** " + ", ".join(c["id"] for c in prov)
    return note


def render_status(scope, out, title=None, audience=None):
    c = scope["counts"]
    h = scope["health"]
    md = [f"# {title or 'Weekly status report'}" + (f" ({audience} view)" if audience else ""),
          f"_{scope['freshness_line']}_", "",
          f"**Health:** {h['level']}" + (f" ({'; '.join(h['reasons'])})" if h["reasons"] else ""), "",
          "| Done | In Progress | Blocked | To Do | Total |", "|---|---|---|---|---|",
          f"| {c['Done']} | {c['In Progress']} | {c['Blocked']} | {c['To Do']} | {c['total']} |", ""]
    for s in STATUSES:
        ts = [t for t in scope["tasks"] if t["status"] == s]
        if ts:
            md.append(f"**{s}**")
            md += [f"- {t['id']} {t['name']} ({t['assignee']}, due {t['due']})" for t in ts]
            md.append("")
    if scope["blocked"]:
        md.append("**Blocked items**")
        for tid in scope["blocked"]:
            t = next(x for x in scope["tasks"] if x["id"] == tid)
            md.append(f"- {t['id']} {t['name']}: {t['description']}")
        md.append("")
    if scope.get("upcoming_milestones"):
        md.append("**Upcoming milestones**")
        md += [f"- {m['name']} (due {m['due']})" for m in scope["upcoming_milestones"]]
        md.append("")
    md.append(_narr(out))
    return "\n".join(md) + _conflict_note(scope) + FOOT


def render_plan(scope, out):
    md = ["# Project plan", "",
          "**Goals (from the project description):** " + (" ".join(scope["goals"]) or "none stated"), "",
          "| Phase | Name | Weeks | Dates | Milestones and deliverables |", "|---|---|---|---|---|"]
    for p in scope["phases"]:
        ms = "; ".join(m["name"] for m in scope["milestones"] if m["phase"] == p["phase"])
        md.append(f"| {p['phase']} | {p['name']} | {p['start_week']} to {p['end_week']} | "
                  f"{p['start_date']} to {p['end_date']} | {ms} |")
    md += ["", f"_Dates assume the project starts {scope['project_start']} (assumption, confirm)._", "", _narr(out)]
    return "\n".join(md) + _conflict_note(scope) + FOOT


def render_risk(scope, out, ranked_ids=None):
    reg = {r["risk_id"]: r for r in scope["risks"]}
    ids = ranked_ids or list(reg)
    md = ["# Risk assessment", "", "| ID | Category | Risk | Impact | Mitigation |", "|---|---|---|---|---|"]
    for rid in ids:
        r = reg[rid]
        md.append(f"| {rid} | {r['category']} | {r['risk_challenge']} | {r['impact']} | {r['mitigation_strategy']} |")
    md += ["", _narr(out)]
    return "\n".join(md) + FOOT


def render_milestones(scope, out, tracking=False):
    md = ["# " + ("Blocked and at-risk tasks" if tracking else "Upcoming milestones"),
          f"_{scope['freshness_line']}_", ""]
    if not tracking:
        md += [f"- {m['name']} (phase {m['phase']}, due {m['due']})" for m in scope["upcoming_milestones"]] or ["- none in window"]
        md.append("")
    md.append("**Blocked or at risk**")
    if scope["at_risk"]:
        for r in scope["at_risk"]:
            t = next(x for x in scope["tasks"] if x["id"] == r["id"])
            md.append(f"- {t['id']} {t['name']} ({t['assignee']}, due {t['due']}): {', '.join(r['reasons'])}")
    else:
        md.append("- none")
    md += ["", _narr(out)]
    return "\n".join(md) + _conflict_note(scope) + FOOT


def render_resource(pack):
    md = ["# Workload by person (counts only)", f"_{pack['freshness_line']}_", "",
          "| Person | Total | Open | Done | In Progress | Blocked | To Do |", "|---|---|---|---|---|---|---|"]
    for name, w in pack["workload"].items():
        b = w["by_status"]
        md.append(f"| {name} | {w['total']} | {w['open']} | {b.get('Done', 0)} | {b.get('In Progress', 0)} | "
                  f"{b.get('Blocked', 0)} | {b.get('To Do', 0)} |")
    md.append("\nCounts and due dates only. Mira does not rate individuals.")
    return "\n".join(md) + FOOT


def render_update(scope, out, audience, sprint):
    subject = f"{sprint or 'Weekly'} progress update"
    c = scope["counts"]
    body = [f"Subject: {subject}", "", f"Audience: {audience or 'leadership'}", "",
            f"_{scope['freshness_line']}_", "",
            f"Tasks in scope: {c['total']} (Done {c['Done']}, In Progress {c['In Progress']}, "
            f"Blocked {c['Blocked']}, To Do {c['To Do']}). Health: {scope['health']['level']}.", "",
            _narr(out, refs=False)]
    return "\n".join(body) + _conflict_note(scope) + FOOT


def render_held(request_type, conflicts):
    md = [f"# {request_type.capitalize()} output held", "",
          "Mira found data conflicts that affect this output and no signed decision covers them. "
          "Nothing was generated. Take each item to its data owner, then sign a decision.", ""]
    for c in conflicts:
        md.append(f"- **{c['id']}** ({c['type']}): {c['evidence']}" + (f" [{c['note']}]" if c.get("note") else ""))
    return "\n".join(md)


def render_insufficient(request_type, ask):
    return (f"# Not enough information for a {request_type}\n\nMira will not guess. Please provide:\n\n"
            + "\n".join(f"- {a}" for a in ask))


REFUSALS = {
    "people_rating": "Mira does not rate or judge individuals. It can show workload counts and due dates per person instead.",
    "legal": "Mira cannot give legal advice. Please take this to your legal team.",
    "financial": "Mira cannot give financial advice. Please take this to your finance team.",
    "hr": "Mira cannot support HR or personnel decisions. Please take this to HR.",
    "other": "That request is outside what Mira does (plans, risks, status and milestones from your project files).",
}


def render_declined(reason):
    return "# Request declined\n\n" + REFUSALS.get(reason or "other", REFUSALS["other"])
