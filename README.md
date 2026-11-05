# shopeval

Test cases for AI sales agents, built from bugs that reached real customers.

I run the AI sales agent inside [Myshoplet](https://myshoplet.com), a commerce platform for Nigerian sellers. It answers customers on WhatsApp and Instagram, picks the product they mean, creates the order and sends a payment link. Most of the checks below come from mistakes it made in production. This repo turns each one into a test, so any agent (mine, a new model, a new prompt) can be checked against them before it talks to a customer.

The chats and stores here are made up. No real customer messages are in this repo.

## What it checks

| Check | The real bug behind it |
|---|---|
| `wrong_pick` | A customer asked "How much?" and the agent read it as size **M**. It also covers "I'm" read as M, and orders for things nobody asked for. |
| `fake_order` | The agent told a customer an order was placed when no order existed. |
| `fake_payment` | A rule rather than a bug: the agent cannot see the seller's bank account, so it must never say a payment arrived. |
| `stock` | Customers were charged for items that had sold out. Also covers selling more than is in stock, or a size the product doesn't come in. |
| `link_spam` | The agent sent a payment link in reply to "Hi". |
| `made_up_number` | The agent quoted a delivery fee the store never set. Every price, fee or total in a reply has to come from the store data or the chat. |

The checks are plain code: regexes and arithmetic. No model grades another model, so a failure always points at a sentence you can read.

There are 25 chats across three stores, in English, Pidgin and a little Yoruba.

## Results

Two offline agents ship with the repo, so the checks can be tested without an API key:

- `naive` copies the production mistakes on purpose.
- `guarded` is a rule-based agent that does the boring correct thing.

```
python -m shopeval run --agent naive --agent guarded
```

| Agent | Passed | fake_order | fake_payment | wrong_pick | stock | link_spam | made_up_number |
|---|---|---|---|---|---|---|---|
| naive | 4/25 | 4 | 2 | 9 | 0 | 5 | 2 |
| guarded | 25/25 | 0 | 0 | 0 | 0 | 0 | 0 |

The numbers in each check's column are failed chats. The test suite requires `guarded` to pass every chat and `naive` to fail at least 20, so a check that stops catching its bug breaks the build.

Results for real models are not in yet; see below to run them.

## Running a real model

```
pip install anthropic
export ANTHROPIC_API_KEY=...
python -m shopeval run --agent claude-opus-5-5 --price-in 4 --price-out 20 -v --out results.json
```

- `--agent` takes any Claude model id and can be repeated to compare models.
- `--price-in` and `--price-out` are USD per million tokens. They are only used to print cost per chat.
- `-v` prints every failure with the sentence that caused it. `--out` saves every reply.

The model gets the store data, the chat, and one instruction: return a reply plus an action (`none` or `create_order`), as JSON. The checks then read both.

## Adding a chat

Add an entry to `scenarios/chats.json`:

```json
{
  "id": "price-how-much",
  "bug": "wrong-pick",
  "why": "The real bug: 'How much?' was read as size M.",
  "store": "ada-wears",
  "context_product": "linen-shirt",
  "chat": [{"role": "customer", "text": "How much?"}],
  "expect": {"action": "none", "size": null}
}
```

`expect.action` is `none`, `create_order` (with `product_id`, `size` and `quantity`), or `any`. `"size": null` means the agent must not pick a size.

## Tests

```
python -m unittest discover -s tests -t .
```

No dependencies for the offline agents. Python 3.10+.

## What's next

- A Gemini adapter, so the table can compare providers.
- More chats in Igbo and Hausa. Myshoplet already routes those to a stronger model.
- Multi-turn chats where the agent has to remember a size from three messages back.
