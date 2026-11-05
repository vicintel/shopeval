"""Checks the Claude adapter's request and parsing without calling the API."""

import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from shopeval.scenario import load

try:
    import anthropic  # noqa: F401
except ImportError:  # the offline agents need no SDK
    anthropic = None


@unittest.skipIf(anthropic is None, "anthropic not installed")
class ClaudeAgentTest(unittest.TestCase):
    def test_builds_request_and_parses_reply(self):
        from shopeval.agents.claude import ClaudeAgent

        sc = next(s for s in load() if s.id == "buy-two-after-question")
        body = {"reply": "Done, 2 pairs.", "action": {"type": "create_order", "product_id": "white-sneakers", "size": "42", "quantity": 2}}
        fake = SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps(body))],
            usage=SimpleNamespace(input_tokens=900, output_tokens=60),
        )
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            agent = ClaudeAgent()
        with mock.patch.object(agent.client.messages, "create", return_value=fake) as create:
            reply = agent.respond(sc)

        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-opus-5-5")
        self.assertEqual([m["role"] for m in kwargs["messages"]], ["user", "assistant", "user"])
        self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(reply.action["quantity"], 2)
        self.assertEqual((reply.input_tokens, reply.output_tokens), (900, 60))


if __name__ == "__main__":
    unittest.main()
