"""Tracing. Always writes a local JSONL trace. Also sends to Langfuse when LANGFUSE_PUBLIC_KEY
and LANGFUSE_SECRET_KEY are set and the langfuse package is installed (self-hosted: set
LANGFUSE_HOST). Langfuse errors never break a run. The Langfuse hooks cover SDK v3 and v2
but have not been tested against your install yet."""
import json
import os
import time
import uuid
from contextlib import contextmanager


class Tracer:
    def __init__(self, path="traces/mira_traces.jsonl", langfuse=True, trace_id=None):
        self.path = path
        # trace_id lets several Langflow nodes add spans to one shared trace
        self.trace_id = trace_id or uuid.uuid4().hex
        self.lf, self.ver, self._v2_trace = None, None, None
        if langfuse and os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
            try:
                from langfuse import get_client  # SDK v3
                self.lf, self.ver = get_client(), 3
            except Exception:
                try:
                    from langfuse import Langfuse  # SDK v2
                    self.lf, self.ver = Langfuse(), 2
                    self._v2_trace = self.lf.trace(id=self.trace_id, name="mira_run")
                except Exception:
                    self.lf = None

    @contextmanager
    def span(self, name, input=None):
        holder, t0, cm, sp = {}, time.time(), None, None
        if self.lf and self.ver == 3:
            try:
                try:
                    cm = self.lf.start_as_current_span(name=name, input=input,
                                                       trace_context={"trace_id": self.trace_id})
                except TypeError:
                    cm = self.lf.start_as_current_span(name=name, input=input)
                sp = cm.__enter__()
            except Exception:
                cm = None
        try:
            yield holder
        finally:
            ms = int((time.time() - t0) * 1000)
            rec = {"trace_id": self.trace_id, "name": name, "ms": ms, "input": input,
                   "output": holder.get("output"), "meta": holder.get("meta")}
            try:
                os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, default=str) + "\n")
            except OSError:
                pass
            try:
                if cm is not None:
                    sp.update(output=holder.get("output"), metadata=holder.get("meta"))
                    cm.__exit__(None, None, None)
                elif self.lf and self.ver == 2:
                    self._v2_trace.span(name=name, input=input, output=holder.get("output"),
                                        metadata=holder.get("meta"))
            except Exception:
                pass

    def flush(self):
        try:
            if self.lf:
                self.lf.flush()
        except Exception:
            pass
