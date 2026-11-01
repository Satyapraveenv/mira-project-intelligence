"""Checks the deterministic Mira tests against the real CSVs. LLM-written tests
are scored in Langfuse against tests/tests.csv instead."""
import copy, csv, sys
sys.path.insert(0, ".")
from datetime import date
import mira_facts as m

D = "data"
ok, bad = [], []

def check(name, cond, detail=""):
    (ok if cond else bad).append(name)
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  " + str(detail)))

p = m.facts_pack(D)
# T10
check("T10 counts", p["counts"] == {"Done": 5, "In Progress": 3, "Blocked": 1, "To Do": 16, "total": 25}, p["counts"])
# T5 and T12
check("T5 sprint 3", sorted(p["by_sprint"]["Sprint 3"]) == ["T007", "T008", "T009", "T025"], p["by_sprint"]["Sprint 3"])
check("T12 sprint 2", sorted(p["by_sprint"]["Sprint 2"]) == ["T004", "T005", "T006"], p["by_sprint"]["Sprint 2"])
# T8
ids = sorted(r["id"] for r in p["at_risk"])
check("T8 at risk", ids == ["T006", "T024"], ids)
check("T8 blocked", p["blocked"] == ["T024"], p["blocked"])
# T11
names = sorted(x["name"] for x in p["upcoming_milestones"])
check("T11 milestones", names == ["Current systems audit report", "Gap analysis report"] and
      all(x["due"] == "2026-04-26" for x in p["upcoming_milestones"]), names)
check("T1 structure 8 phases 14 milestones", len(p["phases"]) == 8 and len(p["milestones"]) == 14,
      (len(p["phases"]), len(p["milestones"])))
check("T3/T7 risk register 10", [r["risk_id"] for r in p["risks"]] == [f"R{i:02d}" for i in range(1, 11)])
# R1
p1 = m.facts_pack(D, as_of=date(2026, 4, 25))
ids = sorted(r["id"] for r in p1["at_risk"])
check("R1 at risk 25 Apr", ids == ["T006", "T007", "T008", "T024", "T025"], ids)
check("R1 T006 overdue", "T006" in p1["overdue"], p1["overdue"])
# R2
cids = sorted(c["id"] for c in p["conflicts"])
exp = sorted(["C-PHASE-T017", "C-PHASE-T018", "C-PHASE-T019", "C-PHASE-T020", "C-PHASE-T022", "C-PHASE-T023", "C-BOARD-END"])
check("R2 seven conflicts", cids == exp, cids)
check("R2 unmapped labels", sorted(x["task"] for x in p["needs_explicit_mapping"]) == ["T024", "T025"])
tl, rk, tb = m.load(D)
ctrl = copy.deepcopy(tb)
new_due = {"T017": "2026-07-07", "T018": "2026-07-08", "T019": "2026-07-21", "T020": "2026-07-22",
           "T022": "2026-09-02", "T023": "2026-09-10"}
for r in ctrl:
    if r["task_id"] in new_due:
        r["due_date"] = new_due[r["task_id"]]
pc = m.facts_pack(D, tasks_override=ctrl)
check("R2 clean control zero conflicts", pc["conflicts"] == [], [c["id"] for c in pc["conflicts"]])
# R7
p7 = m.facts_pack(D, as_of=date(2026, 10, 21))
check("R7 out of range raised", any(c["id"] == "C-ASOF" for c in p7["conflicts"]))
check("R7 twenty overdue", len(p7["overdue"]) == 20, len(p7["overdue"]))
check("R7 status held", "status" in m.held_outputs(m.apply_decisions(p7, [])))
# R8
c17 = next(c for c in p["conflicts"] if c["id"] == "C-PHASE-T017")
dec = [m.new_decision(c17, "data is correct", "Satya", "Confirmed with project manager")]
pa = m.apply_decisions(m.facts_pack(D), dec)
check("R8 resolved before edit", next(c for c in pa["conflicts"] if c["id"] == "C-PHASE-T017")["status"] == "resolved")
edit = copy.deepcopy(tb)
for r in edit:
    if r["task_id"] == "T017":
        r["due_date"] = "2026-06-24"
pe = m.apply_decisions(m.facts_pack(D, tasks_override=edit), dec)
c_after = next(c for c in pe["conflicts"] if c["id"] == "C-PHASE-T017")
check("R8 expired after edit", c_after["status"] == "open" and "expired" in c_after.get("note", ""), c_after)
# R9 and C3
p9 = m.apply_decisions(m.facts_pack(D, stated_counts={"Done": 3}), [])
c9 = next((c for c in p9["conflicts"] if c["id"] == "C-COUNT-Done"), None)
check("R9 stated count conflict", c9 is not None and c9["evidence"] == {"status": "Done", "stated": 3, "board": 5}, c9)
check("C3 status held, risk not held", "status" in m.held_outputs(p9) and "risk" not in m.held_outputs(p9), m.held_outputs(p9))
# Sufficiency gate: T2, T4, T6, T9
for tid, rtype in [("T2", "plan"), ("T4", "risk"), ("T6", "status"), ("T9", "plan")]:
    good, miss, ask = m.sufficiency(rtype, set())
    check(f"{tid} insufficient and asks", (not good) and bool(ask), (miss, ask))
good, _, _ = m.sufficiency("plan", {"description", "timeline", "risks", "tasks"})
check("T1 sufficient with ABCDE sources", good)
# Repeatability (R10, code part)
check("R10 deterministic repeat", m.facts_pack(D)["counts"] == m.facts_pack(D)["counts"] and
      m.facts_pack(D)["at_risk"] == m.facts_pack(D)["at_risk"])

print(f"\n{len(ok)} passed, {len(bad)} failed")
sys.exit(1 if bad else 0)
