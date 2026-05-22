"""Shared LLM proxy types + per-model pricing (USD per 1M tokens)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Provider = Literal["gemini", "anthropic"]
Reason = Literal["nl_to_cypher", "chain_triage", "embed", "probe"]


class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMResponse(BaseModel):
    provider: Provider
    model: str
    text: str
    usage: LLMUsage
    cost_usd: float
    duration_ms: int


class LLMError(Exception):
    """Provider call failed (network, 4xx, 5xx). Carries provider + status if known."""

    def __init__(self, message: str, *, provider: Provider, status: int | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status = status


class KillSwitchTripped(Exception):
    """Global daily-spend cap exceeded. Surface as HTTP 503."""


# Pricing snapshot — USD per 1M tokens. Used to compute call cost on the
# response path. Update when provider pricing changes; we deliberately do
# not call provider APIs to retrieve pricing.
PRICING: dict[tuple[Provider, str], tuple[float, float]] = {
    # provider, model -> (prompt_$/MT, completion_$/MT)
    ("gemini", "gemini-2.5-flash"): (0.30, 2.50),
    ("gemini", "gemini-2.5-pro"): (1.25, 10.00),
    ("gemini", "text-embedding-004"): (0.025, 0.0),
    ("anthropic", "claude-sonnet-4-5-20250929"): (3.00, 15.00),
    ("anthropic", "claude-opus-4-5-20250929"): (15.00, 75.00),
}


def cost_for(provider: Provider, model: str, usage: LLMUsage) -> float:
    rate = PRICING.get((provider, model))
    if rate is None:
        return 0.0
    p_rate, c_rate = rate
    return (usage.prompt_tokens * p_rate + usage.completion_tokens * c_rate) / 1_000_000
