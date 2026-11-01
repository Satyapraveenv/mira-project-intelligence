# Mira: Design and Eval Plan

Applied Agentic AI for PMs/TPMs capstone. Built with the IK assignment framework (Stages 1 to 4). Status: planning complete, build starting. Date: 21 Oct 2026.

## 1. Ambition and constraints
- Ambition: portfolio showcase, built as a real product (PM/TPM mindset), not only to the rubric.
- Time: MVP in about two hours. Build order is tiered so the rubric stays safe if time runs short.
- Platform: LangFlow first with Langfuse for tracing, then n8n as a comparison pass.
- LLM: OpenAI, gpt-4o-mini by default, with a stronger OpenAI model as fallback only if tests show a quality gap.

## 2. Stage 1: the problem
1. Nexora runs many projects, and project managers lead each one and own its plan, task board and risk data.
2. PMs/TPMs coordinate across those projects and across departments.
3. Planning, risk assessment and status reporting are slow, manual and inconsistent.
4. Gathering information across departments adds delay.
5. There is no single governed view of projects, people and programme health.
6. Each audience needs a different level of detail, and today it is rewritten by hand.
7. Milestone problems surface late, in retrospectives.

Users: PM/TPM (primary), project manager (secondary, owns the data), task owners (appear in outputs), audience stakeholders (receive outputs).

Business value: time saved on plans (3 to 4 hours each) and weekly status reports (1 to 2 hours each), consistent quality, early warning, and protection of ABCDE's goals (15% fewer delivery delays, 10% lower operating costs). No savings figure is claimed until measured.

### Assumptions (each goes into the charter)
1. Project start is Mon 30 Mar 2026 (inferred from task due dates).
2. Default as-of date is 20 Apr 2026. It is settable, with a "use today" switch.
3. Project managers exist as a secondary role (not in the brief). Our assumption.
4. Where the CSV and another source disagree, Mira reports the CSV and flags the conflict. Nothing is final until a PM/TPM signs a decision.
5. The task board is the source of truth for status. Freshness is unknown, so every report shows the data-as-of line and stale-board signs.
6. Starting departments are data science, IT and business (the only ones the description names).
7. Designed for many projects, but only ABCDE has real data. Anything else is labelled sample.
8. Meeting notes are out of the MVP. In v2 they appear only as unconfirmed suggestions.
9. Sprint windows are derived from task due dates (no sprint dates in the data).
10. Task to phase link: phase is assigned by the due-date window, the label's implied phase is the cross-check, and mismatches are flagged for sign-off.

### Governance rule
Mira never resolves a conflict. It shows the raw evidence, the PM/TPM takes it to the data owner, and the PM/TPM signs a decision (data correct, typo, more data needed, or proceed as provisional). Decisions are logged with who, when and why, and expire automatically if the underlying data changes. Affected outputs are held. Unaffected outputs still run.

## 3. Stage 2: solution space
| Decision | Chosen | Alternative considered | Why set aside |
|---|---|---|---|
| Overall approach | Hybrid: code for exact work, LLM for language | Manual with templates | Does not fix time or late alerts |
| | | Rule-based only | Cannot write a plan from text or tailor per audience |
| | | LLM only | Can miscount, invent details, vary between runs |
| Counts, dates, workload | Deterministic code | LLM computes them | Wrong counts break trust and T10 |
| Data conflicts | Flag, human signs decision | Mira auto-resolves | Breaks grounding |
| | | Block until resolved | Stops unaffected work |
| Stale boards | Flag with freshness line and warnings | Ignore, or block all | Ignoring hides risk, blocking is too heavy |
| Meeting notes | v2, as unconfirmed suggestions | In MVP | No real notes to ground or test on |
| Portfolio data | One real project, many-project-ready design | Invented demo projects | Breaks the no-invented-data rule |
| Build platform | LangFlow first, then n8n | n8n only, or both at once | LangFlow and Langfuse already installed |
| Governance | Full decision register, built in tiers | Derived checklist only | Chosen for richer product story |

Plain code does: counts, grouping, date checks, conflict and stale detection, workload. The LLM does: reading the request, drafting plans and risk assessments, status narrative, audience tailoring, suggested actions. The LLM never produces a number or ID on its own.

## 4. Stage 3: design
Flow: request, Router, Data Checker (code), sufficiency gate, conflict gate (human), specialist agent, Grounding Verifier (code), Audience Writer, PM/TPM review, release, run record and Langfuse trace.

Layers: Control (router, state, guardrails, data checker), Execution (Planner, Risk Assessor, Status Reporter, Milestone Tracker, then the Synthesizer = Grounding Verifier plus Audience Writer), Reliability (Langfuse, freshness and drift checks, human review, conflict queue, decision log).

Pattern: reflex agents in a Router plus fixed-checks pattern. Six LLM agents (Router, Planner, Risk Assessor, Status Reporter, Milestone Tracker, Audience Writer) and two plain-code components (Data Checker, Grounding Verifier). Pure Sequential would run every agent on every request, pure Router would skip the shared checks, and Hierarchical adds complexity Mira does not need.

Prompting: ordered rules (use only the facts, cite IDs, say so if missing, fixed format), structured JSON output, low temperature, one worked example per refusal case.

Data model: raw read-only entities (project, phase, milestone, task, risk, assignee) and Mira-owned records (conflict, decision, recorded decision, readiness item, run record).

Build tiers:
1. Core: Data Checker, Router, Planner, Risk Assessor, Status Reporter, Grounding Verifier, Langfuse, 12 baseline tests.
2. Extended: Milestone Tracker with as-of date and freshness line, stakeholder Audience Writer.
3. Product layer: conflict queue and decision log, resource view, readiness and decision register, GUI.
4. Stretch: n8n rebuild, fine-tuning experiment.

## 5. Stage 4: proof
### Success criteria
Group A, trust and accuracy
- A1 Task counts match the board exactly: 100% on T10.
- A2 Invented items: 0 across all runs.
- A3 Vague inputs get a request for details, no plan or risks: 4 of 4 (T2, T4, T6, T9).
- A4 T024 always identified, plus overdue or at-risk items for the as-of date: 100% on T8.
- A5 Every claim carries a source ID: 100%.

Group B, speed, consistency and cost
- B1 Machine time per output under 2 minutes (proposed).
- B2 PM/TPM review time measured against the 3 to 4 hour and 1 to 2 hour baselines.
- B3 Repeatability: identical counts and flags across 3 runs, same risk top 3 in at least 2 of 3.
- B4 Format consistency: 100% follow the fixed structure.
- B5 Cost per output tracked by type in Langfuse. Ceiling set after the first full run.

Group C, governance
- C1 Known conflicts detected, 100% of the seeded set, no false alarms on clean data.
- C2 Conflicts resolved by Mira on its own: 0.
- C3 Affected outputs held, unaffected outputs not blocked: 100%.
- C4 Decisions expire when underlying data changes: 100%.
- C5 Outputs released without PM/TPM approval: 0.
- C6 Every logged decision records who, when, why and source: 100%.

Group D, usability
- D1 First useful output in 3 interactions or fewer.
- D2 Audience switching changes wording only, facts identical: 100%.
- D3 Every displayed number traceable to its source row: 100%.
- D4 Usability check with one or two real PMs/TPMs, 3 of 3 tasks unaided (post-MVP if no testers).

### Guardrails
- G1 Mira never writes to the task board, timeline or risk register (read-only tools).
- G2 Mira never sends anything. Export only after PM/TPM approval.
- G3 No web search, browsing or LLM-written code execution on any agent.
- G4 LLM agents see only the facts pack and source text for the current request.
- G5 IDs, counts, dates, statuses, as-of date, freshness line, phase assignments, conflict IDs and citations are written by code.
- G6 Text inside data files is data, never instructions.
- G7 Workload views show counts and due dates only. No performance ratings or personnel recommendations.
- G8 Only needed fields go to the LLM API. A real project needs a data policy check first.
- G9 Out-of-scope requests (legal, financial, HR) are declined and sent to a human.

### Rules the evals depend on
1. At risk means Blocked, or not Done and due within 7 days of the as-of date (inclusive), or overdue. The window is configurable.
2. A milestone is due at the end of its phase's last week.

### Eval set: 22 tests
Full table with inputs and expected results is in tests/tests.csv. Brief's 12 (T1 to T12) plus 10 robustness tests (R1 to R10): as-of shift, conflict detection with clean control, prompt injection, people-rating refusal, out-of-scope refusal, audience consistency, out-of-range date, decision expiry, stated-count conflict, repeatability.

Data layer result: mira_facts.py and run_code_tests.py pass 26 of 26 deterministic checks against the real CSVs (T5, T8, T10, T11, T12, R1, R2, R7, R8, R9, the sufficiency gate, and structure checks). Tests that involve LLM-written text are scored in Langfuse against the same expected results.

## 6. Known data issues found in the inputs
- The brief says 3 Done, the CSV has 5 (T001 to T005). Mira reports the CSV counts: 5 Done, 3 In Progress, 1 Blocked, 16 To Do.
- Six tasks have a label whose phase disagrees with their due-date phase: T017, T018, T019, T020, T022, T023.
- The board's last due date falls in week 19 while the timeline runs to week 24.
- All task due dates (7 Apr to 4 Aug 2026) are before the real current date, so a settable as-of date is required.
- The risk register has no severity scores, so any top-3 ranking is Mira's proposal and must state its criteria.

## 7. Open items
- Measure B2 (review time), B5 (cost ceiling) and D4 (usability check) during the build.
- Charter (Q3) and reflection (Q4) are written after the build, from real results.
- Stage 5 (status report) starts only once the build and tests have real, confirmed results.
