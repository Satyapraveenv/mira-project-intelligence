# Run Mira in Langflow Desktop

Two flows are provided:
- `Mira_Flow_Detailed.json`: the full pipeline on the canvas, one node per stage, every agent prompt editable on its node. Use this for demos and reviews. Explain it with `NODE_CARDS.md`.
- `Mira_Flow.json`: one node that runs the whole tested Python pipeline. Use it as the fallback and to show that all logic is tested Python executed through Langflow.

Both import the same way (steps below) and share the same decisions, runs and traces folders.

### Detailed flow: set up
1. Import `Mira_Flow_Detailed.json`. The canvas has 12 nodes in two rows, left to right, then continuing on the second row.
2. Only the first node (Router Agent) needs settings: Model (`mock` first, then `gpt-4o-mini`), OpenAI key, as-of date, audience, and optional Langfuse keys under its advanced fields.
3. Open the Playground and send the same test requests as below. Every node must run; nodes that are not selected by the router just pass the state through.
4. To show a prompt, open a node and read the System prompt field. Edits on the canvas take effect on the next run.


## Import the flow (easiest)
1. In Langflow Desktop, open your project and click the upload icon next to "Projects" in the left sidebar (or use the flow list menu, then Import).
2. Choose `Mira_Flow.json` from this folder. A flow called "Mira" opens with three nodes: Chat Input, Mira Pipeline, Chat Output.
3. Open the Playground and send: `Which tasks are blocked or at risk of missing their deadline?`
   - The Model field is set to `mock` so it runs without an API key.
   - Expected: a report flagging T024 (blocked) and T006 (due 2026-04-21), plus the list of open data conflicts.
4. Switch Model to `gpt-4o-mini`, paste your OpenAI key in the key field, and send the same request again. The footer shows tokens and cost.
5. Langfuse is optional (advanced fields on the Mira Pipeline node): host (default `http://localhost:3000`), public key, secret key.

## Verified before you got it
The flow was generated from Langflow's own component definitions (lfx 1.12.7) and run headlessly end to end with the mock model: a status request returned the expected report, a milestone request was held for sign-off, and a vague plan request was refused with the right questions. It has not yet run inside Langflow Desktop, so the import is the real test.

## Things to know
- Milestones say "held" until you sign the data conflicts. This is designed behaviour. Plans, risks, status and tracking run immediately.
- To see and sign conflicts, use Terminal in the Implementation folder: `python3 mira_cli.py conflicts` and `python3 mira_cli.py sign ...`.
- Decisions, run records and traces are written to `decisions/`, `runs/` and `traces/` inside the Implementation folder.
- The node reads the Mira modules from the folder in its "Mira folder" field. If you move the folder, update that field.

## If the import fails
- Copy the exact error text to Claude. Fallback: add a Custom Component node, paste the code from `mira_pipeline_component.py`, click Check and Save, and wire it by hand.
- "Mira folder not found": check the Mira folder field and that macOS allows Langflow to read the folder.
- "No module named openai" (real model only): tell Claude, so we switch the call method.

## Rebuilding the JSON
`build_flow.py` regenerates `Mira_Flow.json` from `mira_pipeline_component.py` (needs `pip install lfx`).
