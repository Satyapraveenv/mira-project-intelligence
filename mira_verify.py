"""Grounding Verifier (plain code, no LLM).

Every sentence an agent writes must cite refs that exist in the facts scope, and every
task ID, risk ID, conflict ID, date and number in the text must also exist in that scope.
Anything else is rejected, which is the main defence against invented content (A2, A5).
"""
import re

ID_RE = re.compile(r"\b(?:T\d{3}|R\d{2}|C-[A-Z]+(?:-[A-Za-z0-9]+)?)\b")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
NUM_RE = re.compile(r"(?<![\w.-])\d+(?:\.\d+)?(?![\w-])")
GENERIC_REFS = {"counts", "freshness", "description", "health", "timeline", "register", "board", "goals"}


def tokens(text):
    """Return (ids, dates, numbers) found in a string."""
    s = str(text)
    ids = set(ID_RE.findall(s))
    s2 = ID_RE.sub(" ", s)
    dates = set(DATE_RE.findall(s2))
    s3 = DATE_RE.sub(" ", s2)
    nums = set(NUM_RE.findall(s3))
    return ids, dates, nums


def _walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk(v)
    elif obj is not None:
        yield str(obj)


def universe(scope):
    ids, dates, nums = set(), set(), set()
    for s in _walk(scope):
        i, d, n = tokens(s)
        ids |= i
        dates |= d
        nums |= n
    # Section names of the facts (for example "milestones", "phases", "risks") are valid pointers to real data blocks.
    refs = set(GENERIC_REFS) | ids | {k for k in scope if isinstance(k, str)}
    for m in scope.get("milestones", []) + scope.get("upcoming_milestones", []):
        refs.add(m["name"])
    for p in scope.get("phases", []):
        refs.add(f"P{p['phase']}")
    return {"ids": ids, "dates": dates, "nums": nums, "refs": refs}


def _texts(out):
    yield "summary", out.get("summary", {}).get("text", "")
    for i, it in enumerate(out.get("items", [])):
        yield f"items[{i}]", it.get("text", "")
    for i, it in enumerate(out.get("actions", [])):
        yield f"actions[{i}]", it.get("text", "")
    if out.get("criteria"):
        yield "criteria", out["criteria"]


def verify(out, scope):
    """Return (ok, problems). out is the parsed agent JSON."""
    problems = []
    if not isinstance(out, dict) or not isinstance(out.get("summary"), dict):
        return False, ["schema: summary object missing"]
    if not isinstance(out.get("items", []), list) or not isinstance(out.get("actions", []), list):
        return False, ["schema: items and actions must be lists"]
    u = universe(scope)
    cited = [("summary", out["summary"])] + [(f"items[{i}]", x) for i, x in enumerate(out.get("items", []))] \
        + [(f"actions[{i}]", x) for i, x in enumerate(out.get("actions", []))]
    for where, c in cited:
        if not isinstance(c, dict) or not isinstance(c.get("text"), str):
            problems.append(f"{where}: missing text")
            continue
        refs = c.get("refs")
        if not refs or not isinstance(refs, list):
            problems.append(f"{where}: no refs (every claim needs a source)")
            continue
        for r in refs:
            if r not in u["refs"]:
                problems.append(f"{where}: unknown ref {r!r}")
    for where, text in _texts(out):
        ids, dates, nums = tokens(text)
        for i in sorted(ids - u["ids"]):
            problems.append(f"{where}: unknown id {i}")
        for d in sorted(dates - u["dates"]):
            problems.append(f"{where}: unknown date {d}")
        for n in sorted(nums - u["nums"]):
            problems.append(f"{where}: unknown number {n}")
    return (not problems), problems


def subset_check(base, derived):
    """Audience versions may omit facts but may never add one. Returns (ok, problems)."""
    bi, bd, bn = set(), set(), set()
    for _, t in _texts(base):
        i, d, n = tokens(t)
        bi |= i; bd |= d; bn |= n
    problems = []
    for where, t in _texts(derived):
        i, d, n = tokens(t)
        for x in sorted(i - bi):
            problems.append(f"{where}: id {x} not in base report")
        for x in sorted(d - bd):
            problems.append(f"{where}: date {x} not in base report")
        for x in sorted(n - bn):
            problems.append(f"{where}: number {x} not in base report")
    return (not problems), problems
