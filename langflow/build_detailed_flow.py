"""Builds the detailed Mira flow for Langflow: one node per pipeline stage.

Needs the lfx package (pip install lfx). Usage:
  python build_detailed_flow.py <mira_home_on_this_machine> <mira_home_for_the_json> [model]

It (1) writes one readable component file per stage into detailed/components/, with each agent's
system prompt copied from mira_prompts.py as the editable default, and (2) builds
Mira_Flow_Detailed.json from Langflow's own component definitions (same method as build_flow.py).
The stage logic itself lives in mira_pipeline.py (tested); each node calls one stage function and
passes one JSON state along the wire.
"""
import importlib.util
import json
import os
import sys
import uuid

from lfx.components.input_output import ChatInput, ChatOutput

SRC_HOME, JSON_HOME = sys.argv[1], sys.argv[2]
MODEL = sys.argv[3] if len(sys.argv) > 3 else "mock"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "detailed", "components")
os.makedirs(OUT_DIR, exist_ok=True)
sys.path.insert(0, SRC_HOME)
import mira_prompts as P  # noqa: E402

HEADER = '''import importlib
import json
import os
import sys
from datetime import date, datetime

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.message import Message

MIRA_HOME = "__HOME__"


def _text(v):
    return v.text if hasattr(v, "text") else str(v or "")


def _secret(v):
    if not v:
        return ""
    return v if isinstance(v, str) else v.get_secret_value()


def _load(home):
    # Mira's modules are loaded by name at run time and reloaded on every run, so edits apply at once.
    home = (home or "").strip()
    if not os.path.isfile(os.path.join(home, "mira_pipeline.py")):
        return None, None
    if home not in sys.path:
        sys.path.insert(0, home)
    for loaded in [m for m in sys.modules if m.startswith("mira_")]:
        del sys.modules[loaded]
    return importlib.import_module("mira_pipeline"), importlib.import_module("mira_llm")


def _err_state(msg):
    return json.dumps({"result": {"status": "error", "markdown": msg}})


def _llm(lm, st):
    return lm.MockLLM() if st["model"] == "mock" else lm.OpenAILLM(st["model"])


def _run_node(comp, call):
    mp, lm = _load(comp.mira_home)
    if mp is None:
        return Message(text=_err_state("Mira folder not found or incomplete: " + str(comp.mira_home)))
    try:
        st = json.loads(_text(comp.state))
    except ValueError:
        return Message(text=_err_state("Input is not a Mira state. Connect the previous Mira node."))
    if "route" not in st:
        return Message(text=json.dumps(st))
    tr = mp.Tracer(st.get("trace_path"), st.get("langfuse", False), trace_id=st.get("trace_id"))
    try:
        call(mp, lm, st, tr)
    finally:
        tr.flush()
    comp.status = (st.get("result") or {}).get("status") or "continuing"
    return Message(text=json.dumps(st, default=str))
'''

STATE_IN = '''        MessageTextInput(name="state", display_name="State from previous node"),
        StrInput(name="mira_home", display_name="Mira folder", value=MIRA_HOME, advanced=True),
'''


def comp(cls, display, desc, icon, extra_inputs, body, prompt=None):
    inputs = (STATE_IN if cls != "MiraRouter" else "") + extra_inputs
    code = HEADER.replace("__HOME__", JSON_HOME) + f'''

class {cls}(Component):
    display_name = "{display}"
    description = {desc!r}
    icon = "{icon}"
    name = "{cls}"

    inputs = [
{inputs}    ]
    outputs = [Output(display_name="State", name="state_out", method="run_stage")]

{body}
'''
    return code


def prompt_input(text):
    return f'        MultilineInput(name="prompt", display_name="System prompt", value={text!r}),\n'


ROUTER_INPUTS = '''        MessageTextInput(name="request", display_name="Request", info="What the PM/TPM asks Mira."),
        MultilineInput(name="prompt", display_name="System prompt", value=__P__),
        StrInput(name="as_of", display_name="As-of date (YYYY-MM-DD)", value="2026-04-20"),
        BoolInput(name="use_today", display_name="Use today's date", value=False),
        DropdownInput(name="audience", display_name="Audience", options=["", "engineering", "business", "leadership", "client"], value=""),
        DropdownInput(name="model", display_name="Model", options=["gpt-4o-mini", "mock"], value="mock",
                      info="mock = deterministic stand-in, no API key. Set once here, all agents use it."),
        SecretStrInput(name="openai_api_key", display_name="OpenAI API key", required=False,
                       info="Leave empty to use OPENAI_API_KEY from the environment."),
        StrInput(name="mira_home", display_name="Mira folder", value=MIRA_HOME, advanced=True),
        StrInput(name="stated_done", display_name="Stated Done count (optional)", value="", advanced=True),
        StrInput(name="langfuse_host", display_name="Langfuse host", value="http://localhost:3000", advanced=True),
        SecretStrInput(name="langfuse_public_key", display_name="Langfuse public key", required=False, advanced=True),
        SecretStrInput(name="langfuse_secret_key", display_name="Langfuse secret key", required=False, advanced=True),
'''

ROUTER_BODY = '''    def run_stage(self) -> Message:
        mp, lm = _load(self.mira_home)
        if mp is None:
            return Message(text=_err_state("Mira folder not found or incomplete: " + str(self.mira_home)))
        home = self.mira_home.strip()
        key = _secret(getattr(self, "openai_api_key", None))
        if key:
            os.environ["OPENAI_API_KEY"] = key
        pub, sec = _secret(getattr(self, "langfuse_public_key", None)), _secret(getattr(self, "langfuse_secret_key", None))
        use_lf = bool(pub and sec)
        if use_lf:
            os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"] = pub, sec
            os.environ["LANGFUSE_HOST"] = (self.langfuse_host or "http://localhost:3000").strip()
        llm = lm.MockLLM() if self.model == "mock" else lm.OpenAILLM(self.model)
        as_of = date.today() if self.use_today else datetime.strptime(self.as_of.strip(), "%Y-%m-%d").date()
        stated = {"Done": int(self.stated_done)} if str(self.stated_done or "").strip() else None
        st = mp.new_state(_text(self.request), as_of, mp.mf.DEFAULT_START, (self.audience or None), llm.model,
                          os.path.join(home, "data"), os.path.join(home, "decisions", "decisions.json"), stated)
        st.update(trace_path=os.path.join(home, "traces", "mira_traces.jsonl"),
                  runs_path=os.path.join(home, "runs", "runs.jsonl"), langfuse=use_lf)
        tr = mp.Tracer(st["trace_path"], use_lf, trace_id=st["trace_id"])
        try:
            mp.stage_router(st, llm, tr, self.prompt)
        finally:
            tr.flush()
        r = st["route"]
        self.status = r["type"] + (" (ended early)" if st["result"] else "")
        return Message(text=json.dumps(st, default=str))
'''


def body(call):
    return f'''    def run_stage(self) -> Message:
        return _run_node(self, lambda mp, lm, st, tr: {call})
'''


RENDER_BODY = '''    def run_stage(self) -> Message:
        mp, lm = _load(self.mira_home)
        if mp is None:
            return Message(text="Mira folder not found or incomplete: " + str(self.mira_home))
        try:
            st = json.loads(_text(self.state))
        except ValueError:
            return Message(text="Input is not a Mira state. Connect the previous Mira node.")
        if "route" not in st:
            return Message(text=(st.get("result") or {}).get("markdown", "No output."))
        tr = mp.Tracer(st.get("trace_path"), st.get("langfuse", False), trace_id=st.get("trace_id"))
        try:
            with tr.span("renderer", {"status_before": (st.get("result") or {}).get("status")}) as s:
                mp.stage_render(st, tr)
                s["output"] = {"status": (st.get("result") or {}).get("status")}
        finally:
            mp.record_run(st, st["runs_path"])
            tr.flush()
        res, u = st.get("result") or {}, mp.usage_dict(st)
        self.status = res.get("status", "no output")
        footer = (f"\\n\\n_status: {res.get('status')} | trace: {st['trace_id']} | tokens: {u['prompt_tokens']} in, "
                  f"{u['completion_tokens']} out | cost: ${u['cost_usd']}_")
        return Message(text=res.get("markdown", "No output.") + footer)
'''

SPEC = [
    ("MiraPlanner", "Planner Agent", "plan", P.PLANNER, "Plan narrative per phase. Runs only for plan requests."),
    ("MiraRiskAssessor", "Risk Assessor Agent", "risk", P.RISK, "Explains and ranks risks from the register. Runs only for risk requests."),
    ("MiraStatusReporter", "Status Reporter Agent", "status", P.STATUS, "Status narrative and stakeholder updates. Runs for status and update requests."),
    ("MiraMilestoneTracker", "Milestone Tracker Agent", "milestones", P.MILESTONES, "Milestone and at-risk narrative. Runs for milestone and tracking requests."),
]

files = {}
files["01_router.py"] = comp("MiraRouter", "Router Agent (LLM)",
    "Classifies the request: plan, risk, status, milestones, tracking, update, resource, out of scope or unclear. Never answers it.",
    "bot", ROUTER_INPUTS.replace("__P__", repr(P.ROUTER)), ROUTER_BODY)
files["02_data_checker.py"] = comp("MiraDataChecker", "Data Checker (code)",
    "No LLM. Builds the facts pack from the board, timeline and risk files, finds conflicts, applies signed decisions.",
    "database", "", body("mp.stage_data(st, tr)"))
files["03_gates.py"] = comp("MiraGates", "Gates (code)",
    "No LLM. Sufficiency gate (enough source data?) and conflict gate (unsigned conflicts hold the output for a human).",
    "shield", "", body("mp.stage_gates(st, tr)"))
for i, (cls, disp, which, text, d) in enumerate(SPEC):
    files[f"0{4 + i}_{which}.py"] = comp(cls, disp, d, "bot", prompt_input(text),
        body(f'mp.stage_specialist(st, _llm(lm, st), tr, "{which}", self.prompt)'))
files["08_grounding_verifier.py"] = comp("MiraGroundingVerifier", "Grounding Verifier (code, 1 retry)",
    "No LLM judgement. Rejects any ID, date, number or ref not in the facts. On failure asks the specialist once more, then refuses.",
    "shield-check", "", body("mp.stage_verify(st, _llm(lm, st), tr)"))
files["09_audience_writer.py"] = comp("MiraAudienceWriter", "Audience Writer Agent",
    "Rewrites a status report for engineering, business, leadership or client. May omit facts, never add. Falls back to the base version.",
    "bot", prompt_input(P.AUDIENCE), body("mp.stage_audience(st, _llm(lm, st), tr, self.prompt)"))
files["10_renderer.py"] = comp("MiraRenderer", "Report Renderer (code)",
    "No LLM. Writes every number, ID, date and table, adds the status footer and logs the run.",
    "file-text", "", RENDER_BODY)

for name, code in files.items():
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
        f.write(code)


# ---------------- flow ----------------
def load_cls(path, cls):
    spec = importlib.util.spec_from_file_location("c_" + cls, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, cls)


def enc(d):
    return json.dumps(d, separators=(",", ":")).replace('"', "œ")


def make(cls, x, y, **kw):
    fn = cls(**kw).to_frontend_node()
    return {"id": fn["id"], "type": "genericNode", "position": {"x": x, "y": y},
            "data": fn["data"] | {"id": fn["id"]}, "selected": False, "dragging": False, "width": 340, "height": 420}


def edge(src, dst, field, src_name):
    s_node, d_node = src["data"]["node"], dst["data"]["node"]
    out_def = next(o for o in s_node["outputs"] if o["name"] == src_name)
    f = d_node["template"][field]
    sh = {"dataType": src["data"]["type"], "id": src["id"], "name": src_name, "output_types": out_def["types"]}
    th = {"fieldName": field, "id": dst["id"], "inputTypes": f.get("input_types"), "type": f["type"]}
    return {"source": src["id"], "sourceHandle": enc(sh), "target": dst["id"], "targetHandle": enc(th),
            "id": f"xy-edge__{src['id']}{enc(sh)}-{dst['id']}{enc(th)}",
            "data": {"sourceHandle": sh, "targetHandle": th}, "animated": False, "selected": False}


order = sorted(files)
classes = {n: load_cls(os.path.join(OUT_DIR, n), next(l.split()[1].split("(")[0] for l in files[n].splitlines()
                                                      if l.startswith("class "))) for n in order}
X, Y1, Y2, DX = 60, 80, 620, 420
chat_in = make(ChatInput, X, Y1)
nodes = [make(classes[n], X + DX * (i + 1), Y1, _code=files[n]) if i < 5
         else make(classes[n], X + DX * (i - 5), Y2, _code=files[n]) for i, n in enumerate(order)]
chat_out = make(ChatOutput, X + DX * 5, Y2)
for n_ in nodes:
    t = n_["data"]["node"]["template"]
    if "mira_home" in t:
        t["mira_home"]["value"] = JSON_HOME
nodes[0]["data"]["node"]["template"]["model"]["value"] = MODEL

edges = [edge(chat_in, nodes[0], "request", "message")]
for a, b in zip(nodes, nodes[1:]):
    edges.append(edge(a, b, "state", "state_out"))
edges.append(edge(nodes[-1], chat_out, "input_value", "state_out"))

flow = {"id": str(uuid.uuid4()), "name": "Mira Detailed Pipeline",
        "description": "Mira on the canvas: Router, Data Checker, Gates, four specialist agents, Grounding Verifier, "
                       "Audience Writer, Renderer. Every LLM agent's system prompt is editable on its node.",
        "data": {"nodes": [chat_in] + nodes + [chat_out], "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.45}},
        "is_component": False, "icon": None, "icon_bg_color": None, "gradient": None, "tags": [],
        "endpoint_name": None, "locked": False, "mcp_enabled": False}
out = os.path.join(HERE, "Mira_Flow_Detailed.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)
print("wrote", out, "nodes:", len(flow["data"]["nodes"]), "edges:", len(edges))
