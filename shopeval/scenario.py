"""Loading scenarios, and the reply every agent must return."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "scenarios"


@dataclass
class Scenario:
    id: str
    bug: str
    store: dict
    chat: list[dict]
    expect: dict
    why: str = ""
    context_product: str | None = None
    prior_order: bool = False

    def product(self, product_id: str | None) -> dict | None:
        for p in self.store["products"]:
            if p["id"] == product_id:
                return p
        return None


@dataclass
class AgentReply:
    reply: str
    action: dict = field(default_factory=lambda: {"type": "none"})
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


def load(path: Path | None = None) -> list[Scenario]:
    base = path or ROOT
    stores = json.loads((base / "stores.json").read_text())
    out = []
    for raw in json.loads((base / "chats.json").read_text()):
        store = stores[raw.pop("store")]
        out.append(Scenario(store=store, **raw))
    return out
