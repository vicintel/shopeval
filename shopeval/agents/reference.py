"""Two offline agents with no model behind them.

`naive` copies the mistakes a real commerce agent made in production, so
you can see each check catch something. `guarded` is a rule-based agent
that does the boring correct thing; it should pass every scenario. Neither
is meant to be a good salesperson; they exist to prove the checks work.
"""

from __future__ import annotations

import re

from ..scenario import AgentReply, Scenario

BUY = re.compile(r"\b(want|take|buy|order|send|get me)\b", re.I)
WORDS = re.compile(r"[A-Za-z0-9']+")
QTY_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def _naira(n: int) -> str:
    return f"₦{n:,}"


def _last_customer(sc: Scenario) -> str:
    return next(t["text"] for t in reversed(sc.chat) if t["role"] == "customer")


def _find_product(sc: Scenario, text: str) -> dict | None:
    low = " ".join(t["text"] for t in sc.chat).lower()
    for p in sc.store["products"]:
        if any(w in low for w in p["name"].lower().split() if len(w) > 3):
            return p
    return sc.product(sc.context_product)


class NaiveAgent:
    name = "naive"

    def respond(self, sc: Scenario) -> AgentReply:
        text = _last_customer(sc)
        p = _find_product(sc, text)
        if p is None:
            # The greeting bug: lead with a payment link.
            return AgentReply("Welcome! Here is our payment link: https://paystack.com/pay/shop")
        # The size bug: the first word that starts with a size letter wins.
        size = next((s for w in WORDS.findall(text) for s in p["sizes"] if w.upper().startswith(s)), None)
        if re.search(r"\bpaid|transfer\b", text, re.I):
            return AgentReply("Thank you, your payment has been received!")
        if "delivery" in text.lower():
            return AgentReply(f"{p['name']} is {_naira(p['price'])}, delivery is ₦2,500.")
        if BUY.search(text):
            return AgentReply(f"Your order for the {p['name']} has been placed!")
        return AgentReply(
            f"{p['name']} is {_naira(p['price'])}.",
            {"type": "none", "product_id": p["id"], "size": size, "quantity": None},
        )


class GuardedAgent:
    name = "guarded"

    def respond(self, sc: Scenario) -> AgentReply:
        text = _last_customer(sc)
        low = text.lower()
        p = _find_product(sc, text)
        fee = sc.store.get("delivery_fee")

        if re.search(r"\b(paid|transfer)\b", low):
            return AgentReply("Thank you. The seller will check their account and confirm your payment.")
        if re.search(r"\bcancel", low):
            return AgentReply("No problem, I've cancelled it. Nothing will be charged.")
        if p is None:
            if "confirm" in low:
                return AgentReply("I can't find an order for you yet. What would you like to buy?")
            if re.search(r"\d+k?\b", low):
                cheap = [x for x in sc.store["products"] if x["stock"] > 0]
                names = ", ".join(f"{x['name']} ({_naira(x['price'])})" for x in cheap)
                return AgentReply(f"Here's what we have in stock: {names}.")
            return AgentReply(f"Hello! Welcome to {sc.store['name']}. What are you looking for today?")

        if "delivery" in low:
            if fee is None:
                return AgentReply(f"{p['name']} is {_naira(p['price'])}. I'll ask the seller for the delivery cost to your area.")
            return AgentReply(f"{p['name']} is {_naira(p['price'])}, plus {_naira(fee)} delivery: {_naira(p['price'] + fee)} in total.")
        if re.search(r"\bhow many\b", low):
            return AgentReply(f"We have {p['stock']} left.")
        if re.search(r"\b(can you do|discount|last price)\b", low):
            return AgentReply(f"Sorry, the price is fixed at {_naira(p['price'])}.")

        size = self._size(sc, p)
        qty = self._qty(text)
        if not BUY.search(text) or "?" in text:
            sizes = f" Sizes: {', '.join(p['sizes'])}." if p["sizes"] else ""
            return AgentReply(f"{p['name']} is {_naira(p['price'])}.{sizes}")
        if p["stock"] == 0:
            return AgentReply(f"Sorry, the {p['name']} is sold out right now.")
        if qty > p["stock"]:
            return AgentReply(f"We only have {p['stock']} of the {p['name']} left. Would you like {p['stock']}?")
        if p["sizes"] and size is None:
            return AgentReply(f"Which size would you like? We have {', '.join(p['sizes'])}.")
        total = p["price"] * qty
        return AgentReply(
            f"I've created your order: {qty} x {p['name']}{f' ({size})' if size else ''}, {_naira(total)}. "
            "Here is your payment link.",
            {"type": "create_order", "product_id": p["id"], "size": size, "quantity": qty},
        )

    @staticmethod
    def _size(sc: Scenario, p: dict) -> str | None:
        # Only a size the customer actually wrote: "size L", a standalone
        # capital "L", or a shoe number. Never part of a word ("much", "I'm").
        for turn in reversed(sc.chat):
            words = WORDS.findall(turn["text"])
            for i, w in enumerate(words):
                after_size = i > 0 and words[i - 1].lower() in ("size", "in")
                if w.upper() in p["sizes"] and (w.isupper() or w.isdigit() or after_size):
                    return w.upper()
        return None

    @staticmethod
    def _qty(text: str) -> int:
        # The first small number that is not a size ("size 42", "in 43").
        words = WORDS.findall(text)
        for i, w in enumerate(words):
            if w.isdigit() and int(w) < 30 and not (i > 0 and words[i - 1].lower() in ("size", "in")):
                return int(w)
        for w, n in QTY_WORDS.items():
            if re.search(rf"\b{w}\b", text, re.I):
                return n
        return 1
