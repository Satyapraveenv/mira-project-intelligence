# Mira: AI Project Intelligence Assistant

Mira helps product and programme managers (PMs/TPMs) turn raw project data into plans, risk assessments, status reports, milestone alerts and stakeholder updates, without inventing anything. Every number comes from code, every claim cites its source, and a human decides whenever the data disagrees with itself.

Status: design and eval plan complete. The Tier 1 Python core (router, gates, specialists, grounding verifier, audience writer, tracing hooks, command line) is built and tested with a deterministic mock model (26 data-layer checks and 48 pipeline checks pass). Real-model runs, the LangFlow workflow, Langfuse scoring and the GUI are next. See the roadmap below.

## The problem
Many projects run at once, each led by a project manager who owns its plan, task board and risk data. PMs/TPMs coordinate across those projects and across departments, and they lose hours to work that is slow, manual and inconsistent:
- Plans take 3 to 4 hours each and weekly status reports 1 to 2 hours each.
- Risk assessment quality varies from project to project.
- Each audience (engineering, business, leadership, client) needs a different level of detail, rewritten by hand.
- There is no single governed view across projects, so milestone problems surface late, in retrospectives.

## Design principles
1. **Grounded or silent.** Mira only states what the project files support. If input is too thin it asks for details instead of generating a plan.
2. **Code counts, the LLM writes.** Counts, dates, statuses, IDs, phase links and conflict detection run in plain code. The LLM drafts language around those verified facts and can never produce a number or ID on its own.
3. **Humans decide.** When two sources conflict, Mira shows the raw evidence and holds the affected output. A PM/TPM takes it to the data owner and signs a decision. Decisions are logged (who, when, why) and expire automatically if the underlying data changes.
4. **Draft and notify only.** Mira never edits the task board and never sends anything. Everything is released only after PM/TPM approval.

## Architecture
Router in front of a fixed chain of checks, as a three-layer system:
- **Control:** router, state management, guardrails, Data Checker (code).
- **Execution:** Planner, Risk Assessor, Status Reporter, Milestone Tracker, then a Synthesizer (Grounding Verifier in code plus an Audience Writer).
- **Reliability:** Langfuse tracing and evals, freshness and drift checks, human review, conflict queue and decision log.

Diagrams are in [`architecture/`](architecture/). Open the `.excalidraw` files at excalidraw.com.

## Repository layout
```
architecture/   layered and flow diagrams (Excalidraw)
docs/           Mira_Design_and_Eval_Plan.md: problem, assumptions, design, criteria, guardrails
tests/          tests.csv: 22 tests with hand-computed expected results
data/           see data/README.md (sample data is not included)
mira_facts.py      Data Checker and facts pack (no LLM): counts, at-risk, phases, conflicts, health
mira_pipeline.py   Router, gates, specialists, grounding verifier retry, audience writer
mira_verify.py     Grounding Verifier: every ref, ID, date and number must exist in the facts
mira_render.py     Markdown renderers (all factual content written by code)
mira_prompts.py    Agent prompts: ordered rules, structured JSON output
mira_llm.py        OpenAI client and a deterministic mock model for tests
mira_trace.py      Local JSONL traces plus optional Langfuse
mira_cli.py        Command line: ask, conflicts, sign
run_code_tests.py      26 deterministic data-layer checks
run_pipeline_tests.py  48 end-to-end checks with the mock model
```

## Run the data checks
Place the three sample CSVs in `data/` (see `data/README.md`), then:
```
python3 run_code_tests.py
python3 run_pipeline_tests.py
```
Python 3.9 or newer, standard library only. The `openai` and `langfuse` packages are needed only for real runs.

Try it:
```
python3 mira_cli.py ask "Which tasks are blocked or at risk?" --mock
python3 mira_cli.py conflicts
python3 mira_cli.py sign C-PHASE-T017 --outcome data_correct --by "Your Name" --why "Confirmed with the project manager"
```
Use `--model gpt-4o-mini` (with `OPENAI_API_KEY` set) instead of `--mock` for a real run. The mock model proves the gates and the verifier work. It says nothing about real model quality.

## Run the GUI
The local web GUI runs on `http://127.0.0.1:7860`. It requires the same Python packages as the core (`fastapi`, `uvicorn`, `markdown-it-py`).

```bash
# Install GUI dependencies (first time only)
pip install fastapi uvicorn markdown-it-py

# Start the server (opens browser automatically)
python3 gui/server.py
```

The GUI has four screens:

| Screen | What it does |
|---|---|
| Ask Mira | Paste a request, pick audience and as-of date, submit. Reports are held and explained when data conflicts are detected. |
| Conflict Queue | Lists all open conflicts with raw evidence. A PM/TPM signs each one (decided-by name and rationale required). |
| Dashboard | At-a-glance project health: task counts, health badge, workload by owner, upcoming milestones. |
| Run History | Every run from all sessions. Click a row to expand the full pipeline trace (each agent span timed). |

Mock mode works with no API key. Set `OPENAI_API_KEY` in your environment and select `gpt-4o-mini` in the Model dropdown for a real run.

Added packages (GUI only): `fastapi`, `uvicorn[standard]`, `markdown-it-py`. The four core screens use vanilla JS with no frontend framework or CDN dependencies.

## Evaluation
22 hand-computed tests: 12 baseline tests from the course brief and 10 robustness tests (as-of date shift, conflict detection with a clean control, prompt injection, people-rating refusal, out-of-scope refusal, audience consistency, out-of-range date, decision expiry, stated-count conflict, repeatability). Deterministic tests run in code. Tests that involve LLM-written text are scored in Langfuse against the same expected results.

## Roadmap
- [x] Design, architecture, guardrails and eval plan
- [x] Data Checker and facts pack, with automated checks
- [x] Tier 1 Python core with gates, grounding verifier and tracing hooks (mock-tested)
- [x] Tier 1: real-model runs, Langfuse scoring (17 code-checked tests, 4 LLM judges) and the LangFlow workflow export
- [x] Local web GUI: Ask Mira, Conflict Queue, Dashboard and Run History screens (FastAPI + vanilla JS)
- [x] Real model (gpt-4o-mini) run full-run-4: 17 of 17 code checks, request fit 17 of 17, groundedness 15 of 17, cost $0.009236. R2, R3, R6, R8, R10 are unit tested on the mock model only
- [x] Tier 2: Milestone Tracker, stakeholder Audience Writer and conflict queue
- [ ] Tier 3: resource view, readiness and decision register
- [ ] Tier 4: n8n rebuild for platform comparison, fine-tuning experiment

## Context
Built as the capstone for Interview Kickstart's Applied Agentic AI for PMs/TPMs. The scenario (Nexora delivering an AI adoption project for ABCDE Ltd) comes from the course and is fictional. The course brief and sample data belong to the course and are not included in this repository.

## Author
Satya Praveen Vemuri

## License
MIT. See [LICENSE](LICENSE).
