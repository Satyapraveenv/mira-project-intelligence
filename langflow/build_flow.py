"""Builds Mira_Flow.json (importable in Langflow) from Langflow's own component definitions.

Needs the lfx package (pip install lfx). Usage:
  python build_flow.py <component_file> <out_json> [mira_home] [model]
Nodes are generated with each component's to_frontend_node(), so the templates match what
Langflow itself would produce. Edge handles use Langflow's encoding (double quotes as the
character U+0153).
"""
import importlib.util
import json
import sys
import uuid

from lfx.components.input_output import ChatInput, ChatOutput

comp_file, out = sys.argv[1], sys.argv[2]
mira_home = sys.argv[3] if len(sys.argv) > 3 else None
model = sys.argv[4] if len(sys.argv) > 4 else "mock"

code = open(comp_file, encoding="utf-8").read()
spec = importlib.util.spec_from_file_location("mira_component", comp_file)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def enc(d):
    return json.dumps(d, separators=(",", ":")).replace('"', "œ")


def make(cls, x, y, **kw):
    fn = cls(**kw).to_frontend_node()
    return {"id": fn["id"], "type": "genericNode", "position": {"x": x, "y": y},
            "data": fn["data"] | {"id": fn["id"]}, "selected": False, "dragging": False,
            "width": 320, "height": 300}


chat_in = make(ChatInput, 80, 260)
mira = make(mod.MiraPipeline, 520, 60, _code=code)
chat_out = make(ChatOutput, 1000, 260)

t = mira["data"]["node"]["template"]
t["model"]["value"] = model
if mira_home:
    t["mira_home"]["value"] = mira_home
mira["data"]["node"]["display_name"] = "Mira Pipeline"


def edge(src, src_name, dst, field):
    s_node, d_node = src["data"]["node"], dst["data"]["node"]
    out_def = next(o for o in s_node["outputs"] if o["name"] == src_name)
    f = d_node["template"][field]
    sh = {"dataType": src["data"]["type"], "id": src["id"], "name": src_name, "output_types": out_def["types"]}
    th = {"fieldName": field, "id": dst["id"], "inputTypes": f.get("input_types"), "type": f["type"]}
    return {"source": src["id"], "sourceHandle": enc(sh), "target": dst["id"], "targetHandle": enc(th),
            "id": f"xy-edge__{src['id']}{enc(sh)}-{dst['id']}{enc(th)}",
            "data": {"sourceHandle": sh, "targetHandle": th}, "animated": False, "selected": False}


flow = {
    "id": str(uuid.uuid4()), "name": "Mira",
    "description": "Mira: grounded project intelligence assistant (plans, risks, status, milestones).",
    "data": {"nodes": [chat_in, mira, chat_out],
             "edges": [edge(chat_in, "message", mira, "request"), edge(mira, "report", chat_out, "input_value")],
             "viewport": {"x": 0, "y": 0, "zoom": 0.8}},
    "is_component": False, "icon": None, "icon_bg_color": None, "gradient": None, "tags": [],
    "endpoint_name": None, "locked": False, "mcp_enabled": False,
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(flow, f, indent=2, ensure_ascii=False)
print("wrote", out, "nodes:", len(flow["data"]["nodes"]), "edges:", len(flow["data"]["edges"]))
