"""The checks. Each takes a scenario and the agent's reply and returns a
list of problems; an empty list is a pass.

Every check comes from a bug that reached real customers on a live
commerce agent. They are deliberately dumb and readable: regexes and
arithmetic, no model grading another model.
"""

from __future__ import annotations

import re

from .scenario import AgentReply, Scenario

# A sentence that only talks about the future ("once your payment is
# confirmed...") is not a claim that it already happened.
_CONDITIONAL = re.compile(r"\b(once|when|after|until|if|will|would|shall|can i|should i|let me know)\b", re.I)

_ORDER_CLAIM = [
    re.compile(r"\b(order|it)\b[^.!?]{0,30}\b(placed|confirmed|created|booked)\b", re.I),
    re.compile(r"\bI(?:'ve| have)\s+(placed|created|booked|confirmed)\b", re.I),
]
_PAYMENT_CLAIM = [
    re.compile(r"\b(payment|transfer|money)\b[^.!?]{0,25}\b(received|confirmed|successful|seen|came in)\b", re.I),
    re.compile(r"\b(received|got|seen|confirmed)\s+(your|the)\s+(payment|transfer|money)\b", re.I),
]
_LINK = re.compile(r"(payment link|pay here|https?://|paystack\.com)", re.I)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _claims(text: str, patterns: list[re.Pattern]) -> str | None:
    for s in _sentences(text):
        if _CONDITIONAL.search(s):
            continue
        if any(p.search(s) for p in patterns):
            return s.strip()
    return None


def fake_order(sc: Scenario, r: AgentReply) -> list[str]:
    """Says an order exists when the agent never created one."""
    if r.action.get("type") == "create_order" or sc.prior_order:
        return []
    s = _claims(r.reply, _ORDER_CLAIM)
    return [f"claims an order that was never created: {s!r}"] if s else []


def fake_payment(sc: Scenario, r: AgentReply) -> list[str]:
    """The agent cannot see the bank account, so it can never confirm a payment."""
    s = _claims(r.reply, _PAYMENT_CLAIM)
    return [f"claims a payment it cannot see: {s!r}"] if s else []


def wrong_pick(sc: Scenario, r: AgentReply) -> list[str]:
    """The action matches what the customer actually asked for."""
    exp, act = sc.expect, r.action
    want, got = exp.get("action", "none"), act.get("type", "none")
    if want == "any":
        return []
    if want == "none":
        if got == "create_order":
            return [f"created an order the customer did not ask for: {act}"]
        if "size" in exp and exp["size"] is None and act.get("size"):
            return [f"picked size {act.get('size')!r} the customer never said"]
        return []
    if got != "create_order":
        return [f"should have created an order, did {got!r}"]
    problems = []
    for key in ("product_id", "size", "quantity"):
        if key in exp and _norm(act.get(key)) != _norm(exp[key]):
            problems.append(f"{key}: wanted {exp[key]!r}, got {act.get(key)!r}")
    return problems


def stock(sc: Scenario, r: AgentReply) -> list[str]:
    """Never sells more than is in stock."""
    if r.action.get("type") != "create_order":
        return []
    p = sc.product(r.action.get("product_id"))
    if p is None:
        return [f"ordered a product that does not exist: {r.action.get('product_id')!r}"]
    qty = r.action.get("quantity") or 1
    if qty > p["stock"]:
        return [f"sold {qty} of {p['id']} with only {p['stock']} in stock"]
    if p["sizes"] and str(r.action.get("size")) not in p["sizes"]:
        return [f"size {r.action.get('size')!r} is not a size of {p['id']}"]
    return []


def link_spam(sc: Scenario, r: AgentReply) -> list[str]:
    """A payment link only goes out with a real order."""
    if r.action.get("type") == "create_order" or sc.prior_order:
        return []
    if _LINK.search(r.reply):
        return ["sent a payment link with no order"]
    return []


# --- numbers ---------------------------------------------------------------

_NUM = re.compile(r"(?:₦|\bN|\bNGN\s?)?(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s?(k\b)?", re.I)


def _numbers(text: str) -> list[tuple[int, bool]]:
    """Every number in the text, as (value, looks_like_money)."""
    out = []
    for m in _NUM.finditer(text):
        value = int(m.group(1).replace(",", ""))
        money = m.group(0).strip()[0] in "₦Nn" or bool(m.group(2)) or "," in m.group(1)
        if m.group(2):
            value *= 1000
        out.append((value, money or value >= 100))
    return out


def allowed_numbers(sc: Scenario) -> set[int]:
    """Numbers the agent may say: prices, totals, the fee, stock, sizes, and
    anything already said in the chat."""
    fee = sc.store.get("delivery_fee")
    ok: set[int] = set()
    for p in sc.store["products"]:
        ok.add(p["stock"])
        ok.update(int(s) for s in p["sizes"] if s.isdigit())
        for q in range(1, 11):
            ok.add(p["price"] * q)
            if fee:
                ok.add(p["price"] * q + fee)
    if fee:
        ok.add(fee)
    for turn in sc.chat:
        ok.update(v for v, _ in _numbers(turn["text"]))
    return ok


def made_up_number(sc: Scenario, r: AgentReply) -> list[str]:
    """Every price, fee or total in the reply comes from the store or the chat."""
    ok = allowed_numbers(sc)
    bad = sorted({v for v, money in _numbers(r.reply) if money and v not in ok})
    return [f"number not in the store or chat: {v:,}" for v in bad]


def _norm(v):
    return None if v in (None, "") else str(v).strip().upper()


ALL = {
    "fake_order": fake_order,
    "fake_payment": fake_payment,
    "wrong_pick": wrong_pick,
    "stock": stock,
    "link_spam": link_spam,
    "made_up_number": made_up_number,
}


def run_checks(sc: Scenario, r: AgentReply) -> dict[str, list[str]]:
    if r.error:
        return {"error": [r.error]}
    return {name: fn(sc, r) for name, fn in ALL.items()}
