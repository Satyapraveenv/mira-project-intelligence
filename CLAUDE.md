# Mira: rules for Claude Code

Mira is an AI Project Intelligence Assistant for PMs and TPMs (capstone for Interview Kickstart, Applied Agentic AI). Owner: Satya Praveen Vemuri. Read `README.md`, `docs/Mira_Design_and_Eval_Plan.md` and `GUI_BUILD_BRIEF.md` before you change anything.

## Non-negotiable rules
1. Grounded or silent. Mira never invents a number, ID, date, status, count or citation. Code writes all facts; the LLM only writes short sentences that cite sources; `mira_verify.py` rejects anything unsupported.
2. Humans decide. When sources conflict, Mira shows the raw evidence and holds the output. Only a person signs a decision. The GUI must never auto-resolve or bypass a conflict.
3. Draft and notify only. Mira never sends anything and never edits the task board, timeline or risk files. No send buttons, no write-back to `data/`.
4. Never modify files in `data/`. They are course material and are gitignored. Never commit them.
5. Secrets (OpenAI key, Langfuse keys) come from environment variables or a gitignored `.env`. Never hard-code them, never send them to the browser, never log them.
6. No em dashes or en dashes in any text you write: code comments, UI copy, docs, commit messages. Use a comma, a full stop, or rewrite.
7. Do not put Infuse financial figures or personal data in any file or UI copy.
8. Do not rate or rank individual people anywhere in the UI. Workload views show counts and due dates only.

## Core code is tested and frozen
Files: `mira_facts.py`, `mira_pipeline.py`, `mira_verify.py`, `mira_render.py`, `mira_prompts.py`, `mira_llm.py`, `mira_trace.py`, `mira_cli.py`. Do not edit them. Add new code in a new `gui/` folder and import from the core. If the GUI needs a change in core, stop and propose it with the reason first.

Before and after any work, run both and confirm they pass:
```
python3 run_code_tests.py
python3 run_pipeline_tests.py
```
Run with plain `python3`, not `python3 -I`.

## Commands
- Ask: `python3 mira_cli.py ask "Which tasks are blocked?" --mock`
- Conflicts: `python3 mira_cli.py conflicts`
- Sign: `python3 mira_cli.py sign C-PHASE-T017 --outcome data_correct --by "Name" --why "Reason"`
- Real model: add `--model gpt-4o-mini` with `OPENAI_API_KEY` set. `--mock` is a deterministic stand-in for tests and demos.

## Folder map
`mira_*.py` core, `data/` source files (read only), `decisions/decisions.json` signed human decisions, `runs/runs.jsonl` one record per run, `traces/mira_traces.jsonl` one span per line, `langflow/` flow JSON and components, `architecture/` diagrams, `tests/tests.csv` the 22 evaluation tests.

## Working style
Small steps. Show a plan, then build. Keep the GUI to the four screens in the brief. Prefer standard library or a few well-known packages, and list every package you add. Explain anything you could not test.
