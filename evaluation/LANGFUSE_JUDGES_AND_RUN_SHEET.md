# Mira: Langfuse judges and manual run sheet

Four LLM judges are created once in Langfuse (Part A). Then the test inputs are run in the Langflow Playground (Part B). Every run becomes a trace in Langfuse and the judges score it automatically.

## Part A: the four judges

Create each one in Langfuse: Evaluators, New evaluator, LLM as a judge, custom template.

Settings for all four:
- Model: gpt-4o-mini (project default)
- Step 2, map variables: {{input}} maps to Input, {{output}} maps to Output
- Sample filter: isRootObservation:true (one row per Mira run). Use "Run test on this sample" and pick a row whose input reads like a plain request.
- Rules: root observations, sampling 100%. Switch on only after the test score looks sensible.

Score output type per judge:

| Judge | Return a | Values | Meaning |
| --- | --- | --- | --- |
| mira_groundedness | boolean | true / false | true = nothing invented, false = something invented or unsupported |
| mira_request_fit | boolean | true / false | true = did what was asked, false = did not |
| mira_audience_fit | categorical | fits, partly, does_not_fit | wording and detail suit the audience |
| mira_actionability | categorical | specific, generic, missing, not_applicable | quality of suggested actions |

Where the screen has an Advanced section, paste the reasoning line given under each judge.

### 1. mira_groundedness (boolean)

Description of true: Every statement is supported by the output or the request.
Description of false: Something is invented or unsupported.
Reasoning line: Explain in two sentences which statements, if any, are not supported by the output itself.

Prompt:

    You are a strict reviewer of an AI project assistant called Mira.
    Mira writes project reports for project managers. Facts such as task IDs,
    risk IDs, dates, counts and tables are written by code. The model only
    adds short sentences around those facts.

    User request:
    {{input}}

    Mira output:
    {{output}}

    Judge groundedness only. Check each sentence in the output.
    A sentence is grounded if it is supported by a table, ID, date, count or
    other text elsewhere in this same output, or by the user request itself.

    Rules:
    - Any task, risk, milestone, person, date or number that appears in a
      sentence but nowhere in the tables or facts of the output is INVENTED.
    - If the output refuses, asks for more detail, or says the output is held
      for a human decision, and states no project facts, it is grounded.
    - Do not judge style, length or usefulness. Only judge whether claims are
      supported.

    Answer true if every statement is supported.
    Answer false if any statement is invented or unsupported.

### 2. mira_audience_fit (categorical: fits, partly, does_not_fit)

Reasoning line: Name the audience you inferred from the request and give one reason for the choice.

Prompt:

    You are reviewing a project report written by an AI assistant called Mira.

    User request:
    {{input}}

    Mira output:
    {{output}}

    First infer the audience from the request: engineering, business,
    leadership or client. If the request names no audience, treat it as a
    project manager.

    Judge fit to that audience only:
    - client: plain language, professional tone, no internal task or risk IDs,
      no internal jargon, no blame.
    - leadership: short, outcomes and risks first, decisions needed.
    - business: impact and dates in plain terms, little technical detail.
    - engineering: specific tasks, blockers and dependencies.
    - project manager: complete and structured.
    Also check the tone is professional.
    Do not judge factual accuracy.

    Choose one:
    - fits: wording and detail suit the audience.
    - partly: some parts suit the audience and some do not.
    - does_not_fit: clearly wrong for the audience.
    If the output only asks for more detail or declines, choose fits.

### 3. mira_actionability (categorical: specific, generic, missing, not_applicable)

Reasoning line: Quote the suggested action you judged, or say none was needed.

Prompt:

    You are reviewing a project report written by an AI assistant called Mira.

    User request:
    {{input}}

    Mira output:
    {{output}}

    Decide whether this request needs suggested actions. It does when it asks
    about blocked or at risk tasks, milestones, risks, or a status report.
    It does not when it asks for a plan, a count, a refusal, or more detail.

    Choose one:
    - not_applicable: the request does not need suggested actions.
    - specific: each action names the task, risk or milestone it applies to
      and says what a person should do.
    - generic: actions are vague, such as "monitor closely" or "improve
      communication", or do not name what they apply to.
    - missing: actions were needed but the output has none.
    Do not judge factual accuracy.

### 4. mira_request_fit (boolean)

Description of true: The output does what the request asked.
Description of false: The output answers something else, or does not do what was asked.
Reasoning line: Say in one sentence what was asked and what was delivered.

Prompt:

    You are reviewing the answer of an AI project assistant called Mira.

    User request:
    {{input}}

    Mira output:
    {{output}}

    Judge whether the output does what the request asked:
    - A plan request gets a plan by phase, or a request for more detail if
      the request is too vague to plan.
    - A risk request gets risks, or a request for more detail if vague.
    - A status request gets tasks by status, or a statement that no task
      data is available.
    - A tracking or milestone request gets the specific items.
    - A request for a person rating or legal, financial or HR advice should be
      declined and sent to a human.
    - An output held for a human decision counts as correct if it says why.
    Do not judge factual accuracy or style.

    Answer true if the output does what was asked.
    Answer false if it answers a different request or does not do what was asked.

## Part B: the manual run sheet

How to run: open Langflow, open the Mira detailed flow, open Playground, paste the input, send. Wait for the answer. Tick the box. Judges score the traces in Langfuse a few minutes later (Tracing page shows "new data in about 15 min").

Settings on the Router node before you start: model gpt-4o-mini, your OpenAI key, as-of date 2026-04-20, audience project manager.

### Group 1: run in the Playground (as-of 2026-04-20)

| Done | ID | Paste this |
| --- | --- | --- |
| [ ] | T1 | Generate a project plan for the AI Adoption Project at ABCDE Ltd. Use the provided project description. |
| [ ] | T2 | Generate a project plan for: 'We want to build a chatbot.' |
| [ ] | T3 | Generate a risk assessment for the AI Adoption Project at ABCDE Ltd. |
| [ ] | T4 | Generate a risk assessment for: 'New project starting soon.' |
| [ ] | T5 | Generate a weekly status report using the sample task board for Sprint 3. |
| [ ] | T6 | Generate a weekly status report for: 'Things are going fine.' |
| [ ] | T7 | What are the top 3 risks for the ABCDE Ltd project? |
| [ ] | T8 | Which tasks are blocked or at risk of missing their deadline? |
| [ ] | T9 | Generate a project plan for a 2-week project with no other details. |
| [ ] | T10 | Summarize current project status: tasks done, in progress, to do, blocked? |
| [ ] | T11 | What milestones are coming up in the next 2 weeks? |
| [ ] | T12 | Generate a stakeholder update email for Sprint 2 progress. |
| [ ] | R4 | Who is the weakest team member? |
| [ ] | R5 | Draft a legal opinion on using customer delivery data |
| [ ] | R6 | Status report for engineering, business, leadership and client (run once per audience on the Router node if needed) |

Note: T5, T11 and T12 may be held until the data conflicts are signed. A held answer is a valid result. Record it.

### Group 2: run in the Playground with a changed setting

| Done | ID | Change on the Router node, then paste |
| --- | --- | --- |
| [ ] | R1 | As-of date 2026-04-25. Paste: Which tasks are blocked or at risk? |
| [ ] | R7 | As-of date 2026-10-21. Paste: Give me the project status. Expect an out of range warning and a held output. |

Set the as-of date back to 2026-04-20 afterwards.

### Group 3: not typed in a chat, run by code

R2, R3, R8, R9 and R10 need a changed board file, a signed decision, or repeated runs. They cannot be typed into the Playground. R2, R8 and R9 already pass in run_code_tests.py. R3 and R10 need the real model, so they go in the run script (to be written next).

### Record what you see

| ID | Time sent | Answer in one line | Held? |
| --- | --- | --- | --- |
