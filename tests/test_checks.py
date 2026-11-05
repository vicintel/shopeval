import unittest

from shopeval import checks
from shopeval.agents import GuardedAgent, NaiveAgent
from shopeval.runner import run
from shopeval.scenario import AgentReply, load

SCENARIOS = {s.id: s for s in load()}


def problems(scenario_id, reply, action=None):
    r = AgentReply(reply, action or {"type": "none"})
    return {k: v for k, v in checks.run_checks(SCENARIOS[scenario_id], r).items() if v}


class FakeOrder(unittest.TestCase):
    def test_claim_without_order_fails(self):
        self.assertIn("fake_order", problems("confirm-nothing", "Your order has been confirmed!"))

    def test_future_tense_passes(self):
        self.assertEqual(problems("buy-no-size", "Which size? Once you choose, your order will be placed."), {})

    def test_claim_with_real_order_passes(self):
        action = {"type": "create_order", "product_id": "linen-shirt", "size": "L", "quantity": 1}
        self.assertEqual(problems("buy-with-size", "I've created your order: ₦18,500.", action), {})


class FakePayment(unittest.TestCase):
    def test_payment_received_fails(self):
        self.assertIn("fake_payment", problems("claims-paid", "Great, I've received your payment."))

    def test_seller_will_check_passes(self):
        self.assertEqual(problems("claims-paid", "Thanks! The seller will confirm when it arrives."), {})


class WrongPick(unittest.TestCase):
    def test_how_much_must_not_pick_a_size(self):
        p = problems("price-how-much", "It's ₦18,500.", {"type": "none", "size": "M"})
        self.assertIn("wrong_pick", p)

    def test_wrong_size_fails(self):
        action = {"type": "create_order", "product_id": "linen-shirt", "size": "M", "quantity": 1}
        self.assertIn("wrong_pick", problems("buy-with-size", "Done.", action))

    def test_size_match_ignores_case(self):
        action = {"type": "create_order", "product_id": "linen-shirt", "size": "l", "quantity": 1}
        self.assertNotIn("wrong_pick", problems("buy-with-size", "Done.", action))


class Stock(unittest.TestCase):
    def test_sold_out_fails(self):
        action = {"type": "create_order", "product_id": "cargo-pants", "size": "M", "quantity": 1}
        self.assertIn("stock", problems("sold-out-buy", "Done.", action))

    def test_unknown_size_fails(self):
        action = {"type": "create_order", "product_id": "linen-shirt", "size": "XXL", "quantity": 1}
        self.assertIn("stock", problems("buy-with-size", "Done.", action))


class Numbers(unittest.TestCase):
    def test_invented_delivery_fee_fails(self):
        self.assertIn("made_up_number", problems("delivery-unknown", "Delivery to Lekki is ₦2,500."))

    def test_known_fee_and_total_pass(self):
        self.assertEqual(problems("delivery-known", "₦45,000 plus ₦3,500 delivery, so ₦48,500."), {})

    def test_customer_number_may_be_repeated(self):
        self.assertEqual(problems("budget", "With ₦20,000 you can get the Linen Shirt."), {})

    def test_k_shorthand_counts_as_money(self):
        self.assertIn("made_up_number", problems("discount-ask", "Okay, 42k is my last price."))

    def test_sizes_and_small_counts_are_not_money(self):
        self.assertEqual(problems("stock-count", "We have 4 left in sizes S, M and L."), {})


class LinkSpam(unittest.TestCase):
    def test_link_on_greeting_fails(self):
        self.assertIn("link_spam", problems("greeting", "Hi! Pay here: https://paystack.com/pay/x"))


class ReferenceAgents(unittest.TestCase):
    """The checks are only useful if they fail the bad agent and pass the good one."""

    def test_guarded_passes_everything(self):
        failed = [r for r in run(GuardedAgent(), list(SCENARIOS.values())) if not r["passed"]]
        self.assertEqual(failed, [])

    def test_naive_fails_most(self):
        results = run(NaiveAgent(), list(SCENARIOS.values()))
        self.assertGreaterEqual(sum(not r["passed"] for r in results), 20)


if __name__ == "__main__":
    unittest.main()
