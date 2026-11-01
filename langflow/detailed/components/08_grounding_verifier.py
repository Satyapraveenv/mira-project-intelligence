import importlib
import json
import os
import sys
from datetime import date, datetime

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.message import Message

MIRA_HOME = "/Users/sira/IK/Mira/Implementation"


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


class MiraGroundingVerifier(Component):
    display_name = "Grounding Verifier (code, 1 retry)"
    description = 'No LLM judgement. Rejects any ID, date, number or ref not in the facts. On failure asks the specialist once more, then refuses.'
    icon = "shield-check"
    name = "MiraGroundingVerifier"

    inputs = [
        MessageTextInput(name="state", display_name="State from previous node"),
        StrInput(name="mira_home", display_name="Mira folder", value=MIRA_HOME, advanced=True),
    ]
    outputs = [Output(display_name="State", name="state_out", method="run_stage")]

    def run_stage(self) -> Message:
        return _run_node(self, lambda mp, lm, st, tr: mp.stage_verify(st, _llm(lm, st), tr))

