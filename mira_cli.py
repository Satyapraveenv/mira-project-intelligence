"""Command line for Mira.

  python3 mira_cli.py ask "Which tasks are blocked?" --as-of 2026-04-20 --mock
  python3 mira_cli.py ask "Status report" --audience leadership --model gpt-4o-mini
  python3 mira_cli.py conflicts --as-of 2026-04-20
  python3 mira_cli.py sign C-PHASE-T017 --outcome data_correct --by "Name" --why "Confirmed with the PM"

Set OPENAI_API_KEY for real runs. Set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST
to send traces to Langfuse. --mock uses a deterministic stand-in model (no API key needed).
"""
import argparse
import json
import sys
from datetime import date, datetime

import mira_facts as mf
import mira_pipeline as mp
from mira_llm import MockLLM, OpenAILLM


def _date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mira")
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data", default="data")
    common.add_argument("--as-of", default=str(mf.DEFAULT_AS_OF))
    common.add_argument("--use-today", action="store_true", help="use today's real date as the as-of date")
    common.add_argument("--start", default=str(mf.DEFAULT_START))
    common.add_argument("--decisions", default="decisions/decisions.json")

    a = sub.add_parser("ask", parents=[common])
    a.add_argument("request")
    a.add_argument("--audience", choices=sorted(mp.AUDIENCES))
    a.add_argument("--mock", action="store_true")
    a.add_argument("--model", default="gpt-4o-mini")
    a.add_argument("--stated-done", type=int, help="a stated Done count to compare against the board")
    a.add_argument("--no-langfuse", action="store_true")

    sub.add_parser("conflicts", parents=[common])

    s = sub.add_parser("sign", parents=[common])
    s.add_argument("conflict_id")
    s.add_argument("--outcome", required=True, choices=sorted(mp.OUTCOMES))
    s.add_argument("--by", required=True)
    s.add_argument("--why", required=True)

    args = ap.parse_args(argv)
    as_of = date.today() if args.use_today else _date(args.as_of)
    start = _date(args.start)

    if args.cmd == "ask":
        llm = MockLLM() if args.mock else OpenAILLM(args.model)
        stated = {"Done": args.stated_done} if args.stated_done is not None else None
        res = mp.run(args.request, llm, data_dir=args.data, as_of=as_of, start=start, audience=args.audience,
                     decisions_path=args.decisions, stated_counts=stated, langfuse=not args.no_langfuse)
        print(res["markdown"])
        print(f"\n[status: {res['status']} | trace: {res['trace_id']} | usage: {res['usage']}]")
        return 0

    pack = mf.apply_decisions(mf.facts_pack(args.data, as_of=as_of, start=start), mp.load_decisions(args.decisions))
    if args.cmd == "conflicts":
        for c in pack["conflicts"]:
            print(f"{c['id']:<18} {c.get('status', 'open'):<14} affects {','.join(c['affects']):<22} {c['evidence']}")
        print(f"\n{len(pack['conflicts'])} conflicts. Held outputs: {', '.join(mf.held_outputs(pack)) or 'none'}")
        return 0

    c = next((x for x in pack["conflicts"] if x["id"] == args.conflict_id), None)
    if not c:
        print(f"No conflict {args.conflict_id} at this as-of date.", file=sys.stderr)
        return 1
    d = mp.sign_decision(args.decisions, c, args.outcome, args.by, args.why)
    print("Signed:", json.dumps(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
