"""python -m shopeval run --agent naive --agent guarded"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import agents, runner
from .scenario import load


def main() -> None:
    ap = argparse.ArgumentParser(prog="shopeval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run agents over the scenarios")
    r.add_argument("--agent", action="append", required=True,
                   help="naive, guarded, or a Claude model id such as claude-opus-5-5 (repeatable)")
    r.add_argument("--effort", default="low", help="effort level for Claude agents")
    r.add_argument("--price-in", type=float, default=0, help="USD per million input tokens")
    r.add_argument("--price-out", type=float, default=0, help="USD per million output tokens")
    r.add_argument("--only", help="run only scenarios whose id contains this")
    r.add_argument("--out", type=Path, help="write full results (every reply) to this JSON file")
    r.add_argument("-v", "--verbose", action="store_true", help="print each failure")
    args = ap.parse_args()

    scenarios = load()
    if args.only:
        scenarios = [s for s in scenarios if args.only in s.id]

    rows, full = {}, {}
    for name in args.agent:
        opts = {"effort": args.effort} if name.startswith("claude") else {}
        results = runner.run(agents.make(name, **opts), scenarios)
        rows[name] = runner.summary(results, args.price_in, args.price_out)
        full[name] = results
        if args.verbose:
            for res in results:
                for check, msgs in res["problems"].items():
                    for m in msgs:
                        print(f"  {name} · {res['scenario']} · {check}: {m}")

    print(runner.table(rows))
    if args.out:
        args.out.write_text(json.dumps({"summary": rows, "results": full}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
