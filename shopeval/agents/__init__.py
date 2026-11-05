from .reference import GuardedAgent, NaiveAgent


def make(name: str, **opts):
    if name == "naive":
        return NaiveAgent()
    if name == "guarded":
        return GuardedAgent()
    if name.startswith("claude"):
        from .claude import ClaudeAgent

        return ClaudeAgent(model=name, **opts)
    raise SystemExit(f"unknown agent {name!r}: use naive, guarded, or a Claude model id")
