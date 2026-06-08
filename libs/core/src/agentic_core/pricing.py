"""Gemini token pricing (USD per 1M tokens) and cost estimation. Update as prices
change; keep cheapest-first so the default model stays the cheapest line item."""

# model_id -> (input $/1M tokens, output $/1M tokens)
PRICES_PER_MILLION: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
}

# Fallback for unknown models — priced as flash-lite so cost is never silently zero.
_DEFAULT = PRICES_PER_MILLION["gemini-2.5-flash-lite"]


def estimate_cost_usd(model_id: str, prompt_tokens: int, output_tokens: int) -> float:
    """Estimate the USD cost of one call. Unknown models fall back to the cheapest
    rate (so cost is approximate, never zero) — add the model to PRICES for accuracy."""
    in_rate, out_rate = PRICES_PER_MILLION.get(model_id, _DEFAULT)
    return round((prompt_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate, 8)
