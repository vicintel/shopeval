"""Run an agent over every scenario and summarise the results."""

from __future__ import annotations

from dataclasses import asdict

from .checks import ALL, run_checks
from .scenario import Scenario


def run(agent, scenarios: list[Scenario]) -> list[dict]:
    results = []
    for sc in scenarios:
        reply = agent.respond(sc)
        problems = run_checks(sc, reply)
        results.append({
            "scenario": sc.id,
            "bug": sc.bug,
            "passed": not any(problems.values()),
            "problems": {k: v for k, v in problems.items() if v},
            "reply": asdict(reply),
        })
    return results


def summary(results: list[dict], price_in: float = 0, price_out: float = 0) -> dict:
    n = len(results)
    errors = sum(1 for r in results if "error" in r["problems"])
    by_check = {name: sum(1 for r in results if name in r["problems"]) for name in ALL}
    tin = sum(r["reply"]["input_tokens"] for r in results)
    tout = sum(r["reply"]["output_tokens"] for r in results)
    cost = (tin * price_in + tout * price_out) / 1_000_000
    return {
        "chats": n,
        "passed": sum(r["passed"] for r in results),
        "errors": errors,
        "failed_by_check": by_check,
        "tokens_in": tin,
        "tokens_out": tout,
        "cost_usd_per_chat": cost / n if n and (price_in or price_out) else None,
    }


def table(rows: dict[str, dict]) -> str:
    """Markdown table, one row per agent."""
    checks = list(ALL)
    head = "| Agent | Passed | " + " | ".join(checks) + " | $ / chat |"
    sep = "|---" * (len(checks) + 3) + "|"
    lines = [head, sep]
    for name, s in rows.items():
        cost = f"{s['cost_usd_per_chat']:.4f}" if s["cost_usd_per_chat"] is not None else "-"
        cells = " | ".join(str(s["failed_by_check"][c]) for c in checks)
        err = f" ({s['errors']} errors)" if s["errors"] else ""
        lines.append(f"| {name} | {s['passed']}/{s['chats']}{err} | {cells} | {cost} |")
    return "\n".join(lines)
