"""An agent backed by Claude. Needs `pip install anthropic` and an API key
(or an `ant auth login` profile)."""

from __future__ import annotations

import json

from ..scenario import AgentReply, Scenario

SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "action": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["none", "create_order"]},
                "product_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "size": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "quantity": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            },
            "required": ["type", "product_id", "size", "quantity"],
            "additionalProperties": False,
        },
    },
    "required": ["reply", "action"],
    "additionalProperties": False,
}

SYSTEM = """You are the sales assistant for {name}, an online store in Nigeria. \
You chat with customers on WhatsApp.

Store data (the only source of truth):
{store}

{context}Reply in the customer's language and tone. Keep it short.

Return JSON: "reply" is the message to send. "action" is what the system \
should do. Set action.type to "create_order" only when the customer clearly \
wants to buy now and you know the product, the size (if it has sizes) and \
the quantity, and enough is in stock. The system sends the payment link \
after it creates the order. Otherwise set action.type to "none" and leave \
the other fields null."""


class ClaudeAgent:
    def __init__(self, model: str = "claude-opus-5-5", effort: str = "low"):
        import anthropic  # imported here so the offline agents need no install

        self.client = anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.name = model

    def respond(self, sc: Scenario) -> AgentReply:
        import anthropic

        store = {k: v for k, v in sc.store.items()}
        context = ""
        if sc.context_product:
            p = sc.product(sc.context_product)
            context = f"The customer is looking at: {p['name']} ({p['id']}).\n\n"
        messages = [
            {"role": "user" if t["role"] == "customer" else "assistant", "content": t["text"]}
            for t in sc.chat
        ]
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=SYSTEM.format(name=sc.store["name"], store=json.dumps(store, indent=1), context=context),
                messages=messages,
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": SCHEMA}},
            )
        except anthropic.RateLimitError as e:
            return AgentReply("", error=f"rate limited: {e}")
        except anthropic.APIStatusError as e:
            return AgentReply("", error=f"API error {e.status_code}: {e}")
        except anthropic.APIConnectionError as e:
            return AgentReply("", error=f"connection error: {e}")

        usage = resp.usage
        if resp.stop_reason == "refusal":
            return AgentReply("", input_tokens=usage.input_tokens, output_tokens=usage.output_tokens, error="refusal")
        text = next(b.text for b in resp.content if b.type == "text")
        data = json.loads(text)
        return AgentReply(
            data["reply"], data["action"], input_tokens=usage.input_tokens, output_tokens=usage.output_tokens
        )
