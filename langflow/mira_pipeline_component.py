"""LangFlow custom component: Mira Pipeline (single node, step 1).

Use: in Langflow, drag a "Custom Component" onto the canvas, open its code, replace the code with
this file, then click Check and Save. It runs the tested Mira pipeline from your Implementation
folder, so the gates, grounding verifier and decision log behave exactly as on the command line.

Step 2 splits this into one node per agent so the canvas shows the architecture.
"""
import importlib
import os
import sys
from datetime import date, datetime

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, MessageTextInput, Output, SecretStrInput, StrInput
from lfx.schema.message import Message


def _secret(v):
    if not v:
        return ""
    return v if isinstance(v, str) else v.get_secret_value()


class MiraPipeline(Component):
    display_name = "Mira Pipeline"
    description = "Router, data checker, gates, specialist, grounding verifier and audience writer."
    icon = "bot"
    name = "MiraPipeline"

    inputs = [
        MessageTextInput(name="request", display_name="Request", info="What the PM/TPM asks Mira."),
        StrInput(name="mira_home", display_name="Mira folder", value="/Users/sira/IK/Mira/Implementation",
                 info="Folder that contains mira_pipeline.py, data/ and decisions/."),
        StrInput(name="as_of", display_name="As-of date (YYYY-MM-DD)", value="2026-04-20"),
        BoolInput(name="use_today", display_name="Use today's date", value=False),
        DropdownInput(name="audience", display_name="Audience",
                      options=["", "engineering", "business", "leadership", "client"], value=""),
        DropdownInput(name="model", display_name="Model", options=["gpt-4o-mini", "mock"], value="gpt-4o-mini",
                      info="mock = deterministic stand-in, no API key needed."),
        SecretStrInput(name="openai_api_key", display_name="OpenAI API key", required=False,
                       info="Leave empty to use OPENAI_API_KEY from the environment."),
        StrInput(name="stated_done", display_name="Stated Done count (optional)", value="", advanced=True,
                 info="Compare a stated count against the board. A difference raises a conflict."),
        StrInput(name="langfuse_host", display_name="Langfuse host", value="http://localhost:3000", advanced=True),
        SecretStrInput(name="langfuse_public_key", display_name="Langfuse public key", required=False, advanced=True),
        SecretStrInput(name="langfuse_secret_key", display_name="Langfuse secret key", required=False, advanced=True),
    ]
    outputs = [Output(display_name="Report", name="report", method="run_mira")]

    def run_mira(self) -> Message:
        home = (self.mira_home or "").strip()
        if not os.path.isfile(os.path.join(home, "mira_pipeline.py")):
            return Message(text=f"Mira folder not found or incomplete: {home}")
        # Load Mira's modules by name at run time (no import statements, so Langflow's
        # code check does not mistake them for pip packages). Reloaded on every run so edits apply.
        if home not in sys.path:
            sys.path.insert(0, home)
        for loaded in [m for m in sys.modules if m.startswith("mira_")]:
            del sys.modules[loaded]
        mp = importlib.import_module("mira_pipeline")
        llm_mod = importlib.import_module("mira_llm")
        MockLLM, OpenAILLM = llm_mod.MockLLM, llm_mod.OpenAILLM

        key = _secret(getattr(self, "openai_api_key", None))
        if key:
            os.environ["OPENAI_API_KEY"] = key
        lf_pub = _secret(getattr(self, "langfuse_public_key", None))
        lf_sec = _secret(getattr(self, "langfuse_secret_key", None))
        use_lf = bool(lf_pub and lf_sec)
        if use_lf:
            os.environ["LANGFUSE_PUBLIC_KEY"] = lf_pub
            os.environ["LANGFUSE_SECRET_KEY"] = lf_sec
            os.environ["LANGFUSE_HOST"] = (self.langfuse_host or "http://localhost:3000").strip()

        llm = MockLLM() if self.model == "mock" else OpenAILLM(self.model)
        as_of = date.today() if self.use_today else datetime.strptime(self.as_of.strip(), "%Y-%m-%d").date()
        stated = {"Done": int(self.stated_done)} if str(self.stated_done or "").strip() else None
        text = self.request.text if hasattr(self.request, "text") else str(self.request)

        res = mp.run(
            text, llm, data_dir=os.path.join(home, "data"), as_of=as_of, audience=(self.audience or None),
            decisions_path=os.path.join(home, "decisions", "decisions.json"),
            trace_path=os.path.join(home, "traces", "mira_traces.jsonl"),
            runs_path=os.path.join(home, "runs", "runs.jsonl"),
            stated_counts=stated, langfuse=use_lf,
        )
        u = res["usage"]
        self.status = f"{res['status']} | ${u['cost_usd']}"
        footer = (f"\n\n_status: {res['status']} | trace: {res['trace_id']} | tokens: {u['prompt_tokens']} in, "
                  f"{u['completion_tokens']} out | cost: ${u['cost_usd']}_")
        return Message(text=res["markdown"] + footer)
