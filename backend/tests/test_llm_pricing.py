from __future__ import annotations

from backend.llm.base import LLMUsage, cost_for


def test_gemini_flash_no_cache_matches_legacy_formula() -> None:
    usage = LLMUsage(prompt_tokens=1000, completion_tokens=200)
    expected = (1000 * 0.10 + 200 * 0.40) / 1_000_000
    assert cost_for("gemini", "gemini-3.1-flash-lite", usage) == expected


def test_gemini_flash_cached_input_billed_at_quarter_rate() -> None:
    usage = LLMUsage(
        prompt_tokens=1000, completion_tokens=200, cached_prompt_tokens=800
    )
    uncached_cost = 200 * 0.10
    cached_cost = 800 * 0.10 * 0.25
    completion_cost = 200 * 0.40
    expected = (uncached_cost + cached_cost + completion_cost) / 1_000_000
    assert cost_for("gemini", "gemini-3.1-flash-lite", usage) == expected


def test_anthropic_ignores_cached_tokens_field() -> None:
    usage = LLMUsage(
        prompt_tokens=1000, completion_tokens=200, cached_prompt_tokens=500
    )
    expected = (1000 * 3.00 + 200 * 15.00) / 1_000_000
    assert cost_for("anthropic", "claude-sonnet-4-5-20250929", usage) == expected


def test_cached_tokens_clamped_to_prompt_tokens() -> None:
    # Defensive: cached > prompt would have produced a negative uncached
    # portion before the clamp.
    usage = LLMUsage(
        prompt_tokens=100, completion_tokens=0, cached_prompt_tokens=999
    )
    expected = (100 * 0.10 * 0.25) / 1_000_000
    assert cost_for("gemini", "gemini-3.1-flash-lite", usage) == expected
