"""Runs the brief's 12 baseline tests (T1 to T12) on the deterministic MOCK model and checks each
against the expected result in tests/tests.csv. Writes outputs and a results table.
This proves facts, gates and conflict handling. It does not score real model wording."""
import os, re, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from datetime import date
import mira_facts as mf, mira_pipeline as mp
from mira_llm import MockLLM

H = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
D = os.path.join(H, "data"); OUT = os.path.join(H, "evaluation", "baseline_mock_outputs")
tmp = tempfile.mkdtemp(prefix="mira_base_")
ids = lambda md: set(re.findall(r"\bT\d{3}\b", md))
def ask(text, dec="d.json", **kw):
    kw.setdefault("as_of", date(2026, 4, 20)); llm = MockLLM()
    r = mp.run(text, llm, data_dir=D, decisions_path=os.path.join(tmp, dec),
               trace_path=os.path.join(tmp, "t.jsonl"), runs_path=os.path.join(tmp, "r.jsonl"), langfuse=False, **kw)
    return r, llm
INP = {
 "T1": "Generate a project plan for the AI Adoption Project at ABCDE Ltd. Use the provided project description.",
 "T2": "Generate a project plan for: 'We want to build a chatbot.'",
 "T3": "Generate a risk assessment for the AI Adoption Project at ABCDE Ltd.",
 "T4": "Generate a risk assessment for: 'New project starting soon.'",
 "T5": "Generate a weekly status report using the sample task board for Sprint 3.",
 "T6": "Generate a weekly status report for: 'Things are going fine.'",
 "T7": "What are the top 3 risks for the ABCDE Ltd project?",
 "T8": "Which tasks are blocked or at risk of missing their deadline?",
 "T9": "Generate a project plan for a 2-week project with no other details.",
 "T10": "Summarize current project status: tasks done, in progress, to do, blocked?",
 "T11": "What milestones are coming up in the next 2 weeks?",
 "T12": "Generate a stakeholder update email for Sprint 2 progress."}
res = []
def rec(tid, r, ok, note, extra=""):
    md = r["markdown"]
    open(os.path.join(OUT, f"{tid}.md"), "w").write(f"# {tid}\n\nInput: {INP[tid]}\n\nStatus: {r['status']}\n{extra}\n---\n\n{md}\n")
    res.append((tid, r["status"], ok, note))
nofab = lambda md: not re.search(r"\b(T|R)\d{2,3}\b|\d+%|Phase \d", md)
for t, exp in [("T2", "scope"), ("T4", "project details"), ("T6", "task board"), ("T9", "scope")]:
    r, l = ask(INP[t]); ok = r["status"] == "insufficient" and exp in r["markdown"] and l.calls == ["router"] and nofab(r["markdown"])
    rec(t, r, ok, "Refused, asked for details, no specialist called, nothing invented" if ok else "FAILED")
r, _ = ask(INP["T1"]); rows = [l for l in r["markdown"].splitlines() if re.match(r"\| \d \|", l)]
m = sum(len(l.split("; ")) for l in rows); ok = r["status"] == "ok" and len(rows) == 8 and m == 14 and "reducing delivery delays by 15%" in r["markdown"] and "chatbot" not in r["markdown"].lower()
rec("T1", r, ok, f"{len(rows)} phases, {m} milestones, goals verbatim")
r, _ = ask(INP["T3"]); got = set(re.findall(r"\| (R\d{2}) \|", r["markdown"])); ok = got == {f"R{i:02d}" for i in range(1, 11)}
rec("T3", r, ok, f"{len(got)} risks, all from register R01 to R10")
r, _ = ask(INP["T7"]); top = re.findall(r"\| (R\d{2}) \|", r["markdown"]); ok = len(top) == 3 and "Ranking criteria (proposal)" in r["markdown"]
rec("T7", r, ok, f"Top 3 from register: {', '.join(top)}; ranking criteria labelled as proposal")
r, _ = ask(INP["T5"]); ok = ids(r["markdown"]) == {"T007", "T008", "T009", "T025"}
rec("T5", r, ok, "Exactly T007, T008, T009, T025")
r, _ = ask(INP["T8"]); ok = {"T024", "T006"} <= ids(r["markdown"]) and "T007" not in r["markdown"]
rec("T8", r, ok, "T024 Blocked and T006 at risk flagged; T007 not flagged")
r, _ = ask(INP["T10"]); ok = "| 5 | 3 | 1 | 16 | 25 |" in r["markdown"]
rec("T10", r, ok, "5 Done, 3 In Progress, 1 Blocked, 16 To Do, total 25")
r, _ = ask(INP["T12"]); ok = ids(r["markdown"]) <= {"T004", "T005", "T006"} and "T006" in r["markdown"] and "Pending PM/TPM" in r["markdown"]
rec("T12", r, ok, "Sprint 2 tasks only, draft held for approval")
r, _ = ask(INP["T11"], dec="t11.json"); held = r["status"] == "held" and "C-BOARD-END" in r["markdown"]
pack = mf.facts_pack(D, as_of=date(2026, 4, 20))
for c in pack["conflicts"]:
    if "milestones" in c["affects"]: mp.sign_decision(os.path.join(tmp, "t11.json"), c, "provisional", "Test harness", "TEST SIGN-OFF, not a data owner decision")
r2, _ = ask(INP["T11"], dec="t11.json")
ok = held and r2["status"] == "ok" and "Current systems audit report" in r2["markdown"] and "Gap analysis report" in r2["markdown"] and "Final list of prioritized use cases" not in r2["markdown"].split("Blocked or at risk")[0]
rec("T11", r2, ok, "Held while board conflict unsigned; after a test sign-off shows the 2 milestones due 26 Apr", "Note: first run held, second run after test sign-off.")
tot = sum(1 for x in res if x[2])
order = [f"T{i}" for i in range(1, 13)]; res.sort(key=lambda x: order.index(x[0]))
with open(os.path.join(H, "evaluation", "BASELINE_MOCK_RESULTS.md"), "w") as f:
    f.write("# Baseline T1 to T12: mock model results\n\nModel: deterministic MOCK (not a real model). As-of date 2026-04-20. Checks are code checks against tests/tests.csv. LLM judges: pending (need a working model key). Real model scored run: pending.\n\n| Test | Pipeline status | Code check | What was checked |\n|---|---|---|---|\n")
    for t, s, ok, n in res: f.write(f"| {t} | {s} | {'PASS' if ok else 'FAIL'} | {n} |\n")
    f.write(f"\n**{tot} of 12 pass the code check.** Outputs are in evaluation/baseline_mock_outputs/.\n")
print(open(os.path.join(H, "evaluation", "BASELINE_MOCK_RESULTS.md")).read())
