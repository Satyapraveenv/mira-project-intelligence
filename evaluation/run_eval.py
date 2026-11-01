"""Run the Mira evaluation set and score it.

Modes
  --local   Read tests/tests.csv, run Mira, print and save code check results. No Langfuse needed.
  default   Fetch the Langfuse dataset (mira-eval-22), run each item through Mira, link every run to its
            dataset item as an experiment, and post scores: code_check (true or false) and cost_usd.

Model
  --mock    Deterministic stand-in, no key, no cost. Use this for a dry run.
  (default) gpt-4o-mini. Needs OPENAI_API_KEY in the environment.

Langfuse needs LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in the environment (LANGFUSE_HOST defaults to
https://us.cloud.langfuse.com). Keys are only read from the environment. Never put them in a file.

Examples
  python3 evaluation/run_eval.py --local --mock
  python3 evaluation/run_eval.py --only T10,T5,T2,T8 --run-name first-try
  python3 evaluation/run_eval.py

Code checks cover T1 to T12 plus R1, R4, R5, R7 and R9. The other robustness tests (R2, R3, R6, R8, R10)
need special setup and are scored by the unit test files (run_code_tests.py, run_pipeline_tests.py).
The four Langfuse judges are separate: they run inside Langfuse on the traces this script creates.
"""
import argparse
import csv
import os
import re
import sys
import tempfile
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import mira_facts as mf  # noqa: E402
import mira_llm as ml  # noqa: E402
import mira_pipeline as mp  # noqa: E402

DATASET = "mira-eval-22"
SUPPORTED = [f"T{i}" for i in range(1, 13)] + ["R1", "R4", "R5", "R7", "R9"]
DATA = os.path.join(ROOT, "data")
TMP = tempfile.mkdtemp(prefix="mira_eval_")
OUT_DIR = os.path.join(HERE, "eval_runs")
SIDE = {}      # test_id -> {"status", "usage", "trace_id", "error", "first_status"}
RESULTS = []   # (test_id, passed, note, cost)


def ids(md):
    return set(re.findall(r"\bT\d{3}\b", md))


def nofab(md):
    return not re.search(r"\b(T|R)\d{2,3}\b|\d+%|Phase \d", md)


def run_mira(llm, text, tid, as_of, dec=None, **kw):
    return mp.run(text, llm, data_dir=DATA, as_of=as_of,
                  decisions_path=os.path.join(TMP, dec or f"{tid}.json"),
                  trace_path=os.path.join(OUT_DIR, "traces.jsonl"),
                  runs_path=os.path.join(OUT_DIR, "runs.jsonl"), langfuse=False, **kw)


def execute(llm, tid, text, as_of):
    """Run one test. Returns the markdown. Side information goes into SIDE[tid]."""
    os.makedirs(OUT_DIR, exist_ok=True)
    side = SIDE.setdefault(tid, {})
    kw = {}
    if tid == "R9":
        # the dataset input describes the case. The real request is a status question with a stated count of 3.
        kw["stated_counts"] = {"Done": 3}
        text = "Summarize current project status"
    r = run_mira(llm, text, tid, as_of, **kw)
    if tid == "T11":
        # first run must be held by the board end conflict. Then a clearly labelled TEST sign-off in a
        # temporary file (never the real decision log) lets the milestones run.
        side["first_status"] = r["status"]
        side["first_md"] = r["markdown"]
        pack = mf.facts_pack(DATA, as_of=as_of)
        for c in pack["conflicts"]:
            if "milestones" in c["affects"]:
                mp.sign_decision(os.path.join(TMP, "T11.json"), c, "provisional", "Eval harness",
                                 "TEST SIGN-OFF, not a data owner decision")
        r = run_mira(llm, text, tid, as_of)
    side.update(status=r["status"], usage=r.get("usage", {}), trace_id=r.get("trace_id"))
    return r["markdown"]


def check(tid, md):
    """Code check against the expected result in tests.csv. Returns (passed, note)."""
    st = SIDE.get(tid, {}).get("status")
    if tid in ("T2", "T4", "T6", "T9"):
        want = {"T2": "scope", "T4": "project details", "T6": "task board", "T9": "scope"}[tid]
        ok = st == "insufficient" and want in md and nofab(md)
        return ok, "refused, asked for details, nothing invented" if ok else f"status={st}"
    if tid == "T1":
        rows = [l for l in md.splitlines() if re.match(r"\| \d \|", l)]
        m = sum(len(l.split("; ")) for l in rows)
        ok = st == "ok" and len(rows) == 8 and m == 14 and "reducing delivery delays by 15%" in md
        return ok, f"{len(rows)} phases, {m} milestones"
    if tid == "T3":
        got = set(re.findall(r"\| (R\d{2}) \|", md))
        ok = st == "ok" and got == {f"R{i:02d}" for i in range(1, 11)}
        return ok, f"{len(got)} risks from the register"
    if tid == "T7":
        top = re.findall(r"\| (R\d{2}) \|", md)
        ok = st == "ok" and len(top) == 3 and "Ranking criteria (proposal)" in md
        return ok, "top 3: " + ", ".join(top)
    if tid == "T5":
        ok = st == "ok" and ids(md) == {"T007", "T008", "T009", "T025"}
        return ok, "tasks: " + ", ".join(sorted(ids(md)))
    if tid == "T8":
        ok = st == "ok" and {"T024", "T006"} <= ids(md) and "T007" not in md
        return ok, "flagged: " + ", ".join(sorted(ids(md)))
    if tid == "T10":
        ok = st == "ok" and "| 5 | 3 | 1 | 16 | 25 |" in md
        return ok, "5, 3, 1, 16, total 25" if ok else "counts differ"
    if tid == "T11":
        first = SIDE[tid].get("first_status")
        ok = (first == "held" and "C-BOARD-END" in SIDE[tid].get("first_md", "") and st == "ok"
              and "Current systems audit report" in md and "Gap analysis report" in md
              and "Final list of prioritized use cases" not in md.split("Blocked or at risk")[0])
        return ok, f"first run {first}, then milestones shown after test sign-off"
    if tid == "T12":
        in_scope = "Tasks in scope: 3 (Done 2, In Progress 1" in md and ("T006" in md or "Identify data gaps and quality issues" in md)
        ok = st == "ok" and ids(md) <= {"T004", "T005", "T006"} and in_scope and "Pending PM/TPM" in md
        if ok:
            return ok, "Sprint 2 only, draft held for approval"
        extra = sorted(ids(md) - {"T004", "T005", "T006"})
        return ok, f"status={st}; extra IDs={extra}; in scope 3 tasks={in_scope}; pending footer={'Pending PM/TPM' in md}"
    if tid == "R1":
        got = ids(md)
        ok = {"T006", "T024", "T007", "T025", "T008"} <= got and "T009" not in got
        return ok, "at risk: " + ", ".join(sorted(got))
    if tid in ("R4", "R5"):
        ok = st == "declined" and (tid == "R5" or "workload" in md)
        return ok, "declined" if ok else f"status={st}"
    if tid == "R7":
        ok = st == "held" and "C-ASOF" in md
        return ok, "out of range date held" if ok else f"status={st}"
    if tid == "R9":
        ok = st == "held" and "C-COUNT-Done" in md
        return ok, "stated count conflict held" if ok else f"status={st}"
    return False, "no code check defined"


def get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def parse_input(item):
    inp = get(item, "input")
    if isinstance(inp, str):
        import json
        inp = json.loads(inp)
    return inp or {}


def make_llm(mock):
    if mock:
        return ml.MockLLM()
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set in this terminal. Set it, or use --mock for a dry run.")
    return ml.OpenAILLM("gpt-4o-mini")


def write_report(tag):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"EVAL_RESULTS_{tag}.md")
    total = sum(1 for r in RESULTS if r[1])
    with open(path, "w") as f:
        f.write(f"# Mira eval run: {tag}\n\nCode checks only. LLM judge scores are in Langfuse.\n\n")
        f.write("| Test | Code check | Note | Cost USD |\n|---|---|---|---|\n")
        for tid, ok, note, cost in sorted(RESULTS, key=lambda x: (x[0][0], int(x[0][1:]))):
            f.write(f"| {tid} | {'PASS' if ok else 'FAIL'} | {note} | {cost:.6f} |\n")
        f.write(f"\n**{total} of {len(RESULTS)} pass the code check.** Total cost ${sum(r[3] for r in RESULTS):.6f}\n")
    return path


def main():
    ap = argparse.ArgumentParser(description="Run and score the Mira evaluation set")
    ap.add_argument("--local", action="store_true", help="no Langfuse, read tests/tests.csv")
    ap.add_argument("--mock", action="store_true", help="use the deterministic mock model (no key)")
    ap.add_argument("--only", help="comma separated test IDs, for example T10,T5,T2,T8")
    ap.add_argument("--run-name", help="experiment run name shown in Langfuse")
    args = ap.parse_args()
    only = [t.strip().upper() for t in args.only.split(",")] if args.only else None
    llm = make_llm(args.mock)
    tag = ("mock" if args.mock else "gpt-4o-mini") + ("_local" if args.local else "_langfuse")

    def task(*, item, **kwargs):
        inp = parse_input(item)
        tid = inp["test_id"]
        try:
            return execute(llm, tid, inp["request"], datetime.strptime(inp["as_of"], "%Y-%m-%d").date())
        except Exception as e:  # one failing test must not stop the run
            SIDE.setdefault(tid, {})["error"] = str(e)
            return f"ERROR: {e}"

    def evaluate(tid, output):
        ok, note = check(tid, output if isinstance(output, str) else str(output))
        od = os.path.join(OUT_DIR, "outputs")
        os.makedirs(od, exist_ok=True)
        with open(os.path.join(od, f"{tid}_{tag}.md"), "w") as fh:
            fh.write(output if isinstance(output, str) else str(output))
        if SIDE.get(tid, {}).get("error"):
            ok, note = False, "error: " + SIDE[tid]["error"][:200]
        cost = (SIDE.get(tid, {}).get("usage") or {}).get("cost_usd", 0.0)
        RESULTS.append((tid, ok, note, cost))
        return ok, note, cost

    if args.local:
        rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "tests", "tests.csv")))]
        for r in rows:
            tid = r["test_id"]
            if tid not in SUPPORTED or (only and tid not in only):
                continue
            item = {"input": {"request": r["input"], "as_of": r["as_of"], "test_id": tid}}
            out = task(item=item)
            ok, note, cost = evaluate(tid, out)
            print(("PASS " if ok else "FAIL ") + tid + "  " + note)
        print("Saved", write_report(tag))
        return

    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        if not os.environ.get(k):
            sys.exit(f"{k} is not set in this terminal.")
    os.environ.setdefault("LANGFUSE_HOST", "https://us.cloud.langfuse.com")
    from langfuse import Evaluation, get_client
    lf = get_client()
    lf.auth_check()
    items = []
    for it in lf.get_dataset(DATASET).items:
        tid = parse_input(it).get("test_id")
        if tid in SUPPORTED and (not only or tid in only):
            items.append(it)
        elif tid not in SUPPORTED:
            print("skipping", tid, "(scored by the unit test files)")
    print(f"Running {len(items)} items on {llm.model}")

    def code_check(*, input, output, expected_output=None, metadata=None, **kwargs):
        tid = parse_input({"input": input})["test_id"]
        ok, note, _ = evaluate(tid, output)
        return Evaluation(name="code_check", value=bool(ok), comment=note, data_type="BOOLEAN")

    def cost_usd(*, input, output, expected_output=None, metadata=None, **kwargs):
        tid = parse_input({"input": input})["test_id"]
        u = SIDE.get(tid, {}).get("usage") or {}
        return Evaluation(name="cost_usd", value=float(u.get("cost_usd", 0.0)), data_type="NUMERIC",
                          comment=f"{u.get('prompt_tokens', 0)} in, {u.get('completion_tokens', 0)} out")

    run_name = args.run_name or f"mira-{llm.model}-{datetime.now():%Y%m%d-%H%M}"
    res = lf.run_experiment(name=DATASET, run_name=run_name, data=items, task=task,
                            evaluators=[code_check, cost_usd], max_concurrency=1,
                            metadata={"model": llm.model})
    lf.flush()
    for tid, ok, note, cost in RESULTS:
        print(("PASS " if ok else "FAIL ") + tid + "  " + note)
    print("Saved", write_report(tag))
    print("Experiment:", getattr(res, "dataset_run_url", None))


if __name__ == "__main__":
    main()
