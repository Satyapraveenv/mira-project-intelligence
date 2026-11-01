# Mira node cards (interview script)

Use these to explain each node on the canvas: why this kind of agent, what it does, what it outputs. The pattern is a router in front of a fixed chain of checks. Rule of the whole system: code writes every number, ID, date, status and table; the LLM only writes short sentences that cite sources; a human decides whenever the data disagrees with itself.

## 1. Router Agent (LLM)
- Type: reflex classifier agent. One call, no tools, no memory.
- Why: a request like "which tasks are at risk" or "write an update for the client" must be sent to the right specialist. Classifying is cheap and low risk.
- Task: classify into plan, risk, status, milestones, tracking, update, resource, out of scope or unclear. It never answers the request.
- Output: route (type, sprint, audience, top N, scope reason). Out of scope and unclear requests end the run here.
- Prompt: on the node (System prompt field).

## 2. Data Checker (code, no LLM)
- Why code: counts, dates, phase links and conflict detection must be exact and repeatable. An LLM would drift.
- Task: read the task board, timeline and risk register, build the facts pack, detect conflicts (label vs due date, board end vs timeline, stated count vs board, as-of date out of range), apply signed human decisions.
- Output: facts pack with counts, at-risk tasks, phases, milestones, health and conflict list.

## 3. Gates (code, no LLM)
- Sufficiency gate: if the source data is too thin for the request, Mira asks for details and does not invent a plan.
- Conflict gate: if an unsigned conflict affects the requested output, the output is held. The PM/TPM takes the evidence to the data owner and signs a decision. Mira never resolves conflicts itself.
- Output: continue, insufficient, or held. The workload view is rendered here, from code only.

## 4 to 7. Specialist agents (LLM): Planner, Risk Assessor, Status Reporter, Milestone Tracker
- Type: single-purpose reflex agents, each with its own ordered-rules prompt and structured JSON output.
- Why separate: each task has its own rules and failure modes, and each prompt can be tuned and evaluated alone. Only the one chosen by the Router acts; the others pass the state through.
- Task: write short narrative sentences about the facts in scope, each citing refs (task IDs, risk IDs, phases, milestone names).
- Output: JSON with summary, items, actions. No numbers or dates of their own.
- Planner: phase narrative from the description and goals. Risk Assessor: explain and rank risks from the register. Status Reporter: status narrative and stakeholder updates. Milestone Tracker: milestone and at-risk narrative, also used for tracking.

## 8. Grounding Verifier (code, 1 retry)
- Why: the main defence against hallucination, and it is not an LLM.
- Task: every ref, ID, date and number in the draft must exist in the facts. If not, the specialist gets the exact problems and one retry. If it fails twice, Mira releases nothing.
- Output: verified draft, or a "draft rejected" result.

## 9. Audience Writer Agent (LLM)
- Why: engineering, business, leadership and client need different granularity of the same facts.
- Task: rewrite the verified draft for the chosen audience. It may omit facts but never add any (subset check). On failure, the base version is shown with a note.

## 10. Report Renderer (code)
- Task: write the final markdown. All tables, counts, IDs and dates are rendered here. Adds a footer with status, trace ID, tokens and cost, and logs the run (hash only, not the text).

## Cross-cutting
- Model, API key, as-of date, audience and Langfuse keys are set once on the Router node.
- Tracing: every node adds a span to one shared trace (trace ID in the footer). A local JSONL trace is always written. Langfuse receives the same spans when keys are set.
- Guardrails: read-only data, nothing is sent or written back to the project files, data text is treated as untrusted, no ratings of people, out-of-scope requests refused.
- The state between nodes is one JSON object. Open any node's output to show exactly what it received and produced.
