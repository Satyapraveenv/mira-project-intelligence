# Mira GUI: build brief

## 1. Goal
A local web app for PMs and TPMs to use Mira without the command line, built on the tested core. It must make three things obvious to a reviewer: Mira is grounded, a human resolves data conflicts, and every run is traceable.

Users: a PM or TPM who coordinates several project managers and departments. They do not own the data. They ask Mira for plans, risks, status, milestones and stakeholder updates, and when the data disagrees with itself they take the evidence to the data owner and record a decision.

## 2. Architecture (decided)
- A small local Python server in `gui/` that imports the core and calls it directly. One command starts it and opens the browser: `python3 gui/server.py`.
- A single-page front end served by that server (HTML, CSS and vanilla JavaScript, or a light framework if you justify it).
- Langflow and Langfuse are not required by the GUI. Runs made by the GUI use the same core code, so they write the same run records and traces, and send to Langfuse when its keys are in the environment.
- Server framework: FastAPI with uvicorn if installable, otherwise the standard library `http.server`. Check `python3 --version` first. The core needs Python 3.9 or newer.
- Bind to 127.0.0.1 only. No auth needed locally. Never expose secrets to the browser.

## 3. What the core already gives you
Import these, do not reimplement:
- `mira_pipeline.run(request, llm, data_dir="data", as_of=date, start=date, audience=None, decisions_path="decisions/decisions.json", trace_path="traces/mira_traces.jsonl", runs_path="runs/runs.jsonl", stated_counts=None, langfuse=True)` returns a dict: `status` (ok, held, insufficient, declined, unclear, verification_failed), `markdown` (the full report), `router` (type, audience, sprint, top_n), `trace_id`, `usage` (prompt_tokens, completion_tokens, cost_usd), plus `conflicts` (IDs, when held), `missing`, `problems`.
- `mira_pipeline.sign_decision(path, conflict, outcome, decided_by, rationale)` and `load_decisions(path)`. Outcomes: `data_correct`, `typo`, `more_data_needed`, `provisional`.
- `mira_facts.facts_pack(data_dir, as_of, start, stated_counts=None)` then `mira_facts.apply_decisions(pack, decisions)`. Useful keys: `counts`, `health` (level Red/Amber/Green and reasons), `at_risk`, `blocked`, `overdue`, `upcoming_milestones`, `phases`, `milestones`, `tasks`, `workload`, `conflicts`, `freshness_line`, `assumptions`. Each conflict has `id`, `type`, `evidence`, `affects`, `fingerprint`, and after `apply_decisions` a `status` (open, resolved, awaiting_data).
- `mira_facts.held_outputs(pack)` lists which outputs are blocked by unsigned conflicts.
- Models: `mira_llm.MockLLM()` and `mira_llm.OpenAILLM("gpt-4o-mini")`. Run records are in `runs/runs.jsonl` and spans in `traces/mira_traces.jsonl` (JSON per line, key `trace_id`).
- Defaults: as-of date 2026-04-20 (settable, or "use today"), assumed project start 2026-03-30.

## 4. API (proposed)
- `GET /api/config`: defaults, model options, whether an OpenAI key and Langfuse keys are present (booleans only).
- `POST /api/ask` with request, audience, as_of, use_today, model: returns the `run` result.
- `GET /api/dashboard?as_of=`: health, counts, at-risk, blocked, upcoming milestones, workload counts, conflict summary.
- `GET /api/conflicts?as_of=`: all conflicts with status, evidence, affects, plus `held_outputs`.
- `POST /api/conflicts/{id}/sign`: outcome, decided_by, rationale.
- `GET /api/runs?limit=`: latest run records.
- `GET /api/traces/{trace_id}`: spans for one run.

## 5. Screens
### A. Ask Mira
- Request box, quick prompts (tracking, status, risks top 3, milestones, plan, client update), audience dropdown (none, engineering, business, leadership, client), as-of date with "use today", model toggle (mock, gpt-4o-mini).
- Report panel renders the markdown. Show a status chip (ok, held, insufficient, declined, verification failed), tokens, cost and trace ID with copy.
- Held state: show a prominent banner listing each conflict with its raw evidence and a button to open it in the Conflict queue. Include this disclaimer: "Until these conflicts are resolved, this output is held and the testing phase cannot proceed. Unresolved data conflicts are a project risk." Offer "Log as a risk note" that only copies suggested risk text to the clipboard (Mira does not write to the risk register).
- Insufficient state: show what is missing as a short checklist. Declined state: say what Mira will not do and why.
- A persistent line: "Draft prepared by Mira. Not shared. Pending PM/TPM review and approval." Copy-to-clipboard and download as markdown are fine. No send or email buttons.

### B. Conflict queue and signing
- Table of conflicts: ID, type, task, affects, status, age.
- Detail view: raw evidence shown as a table of fields exactly as returned, never reworded. Show which outputs are held by it.
- Signing form: outcome (four options with one-line explanations), your name, reason (both required). On submit call sign and refresh. Show the decision log with who, when, why.
- Explain expiry: a decision is tied to the data fingerprint and expires when the underlying data changes.

### C. Status dashboard
- Health badge (Red, Amber, Green) with its reasons, shown as text as well as colour.
- Counts by status, upcoming milestones in the window, at-risk and blocked task list (ID, name, due, reason), open conflicts count with link, freshness line and assumptions.
- Workload view: counts and due dates per person only, with the line "Mira does not rate individuals."
- Everything comes from the facts pack. Do not compute new numbers in the browser beyond display formatting.

### D. Run history and traces
- Table from run records: time, request, audience, model, status, tokens, cost, trace ID.
- Click a row to see the spans (router, data_checker, sufficiency_gate, conflict_gate, specialist, grounding_verifier, audience_writer, renderer) with duration and a short output summary. If Langfuse is configured, show a "Open in Langfuse" link using LANGFUSE_HOST and the trace ID.

## 6. Design direction
- Calm, dense, professional. Reads like a delivery governance tool, not a chatbot toy. Light and dark themes that follow the system setting.
- Clear hierarchy: health and held states first. Never rely on colour alone. Readable tables. Works at laptop width and does not break on a phone.
- Copy is plain and short. Never use em dashes or en dashes.
- Empty, loading and error states for every screen. Show server errors in plain words.

## 7. Safety requirements for the GUI
- Never write to `data/`. Only `decisions/`, `runs/` and `traces/` are written, and only through the core functions.
- Treat all text from data files as untrusted: escape HTML, render markdown safely.
- Do not show or log API keys. Show only whether a key is present.
- Do not add any feature that sends, posts or emails anything.

## 8. Acceptance tests
Use the mock model so results are deterministic. As-of 2026-04-20.
1. Ask "Which tasks are blocked or at risk of missing their deadline?": report lists T006 (due 2026-04-21) and T024 (blocked).
2. Ask "Give me the milestone status": status is held, banner lists conflicts C-PHASE-T017 to T023 and C-BOARD-END with raw evidence, and the disclaimer text appears.
3. Sign every listed conflict in the Conflict queue as `data_correct` with a name and reason, then ask the milestone question again: status is ok.
4. Ask "Create a plan for the project": returns the plan table. Ask a vague plan request such as "Generate a project plan for: 'We want to build a chatbot.'": status is insufficient and asks for details.
5. Ask "Which team member is the weakest?": status is declined.
6. Dashboard shows 25 tasks (5 Done, 3 In Progress, 1 Blocked, 16 To Do), health Amber with reasons T006 due in 1 day and T024 blocked.
7. A signing attempt with an empty name or reason is blocked in the UI and by the server.
8. Run history shows every run above with its trace ID, and the span view lists the stages.
9. `python3 run_code_tests.py` and `python3 run_pipeline_tests.py` still pass. `data/` files are unchanged (compare hashes before and after).
10. Search the repo text you wrote for em dashes and en dashes: none.

## 9. Definition of done
All acceptance tests pass in mock mode; one real-model run (gpt-4o-mini) works for tracking and a client update; a README section "Run the GUI" is added; screenshots of the four screens are saved under `docs/screenshots/`; a list of added packages and untested items is reported.

## 10. How to start (paste into Claude Code, run from the Mira folder)
"Read CLAUDE.md and GUI_BUILD_BRIEF.md, then the core files listed in CLAUDE.md. Run both test scripts and confirm they pass. Then show me a short build plan for the four screens and the API, and wait for my approval before writing code."
