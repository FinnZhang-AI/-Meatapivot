"""LLM model pricing catalog — S4-1.

Cost estimates are in **USD cents per 1,000,000 tokens** (i.e. one million
tokens). The ``AIPLLMCall`` table already stores ``estimated_cost_cents``
that the gateway filled in at call time, so this module is mainly used to
*backfill* legacy rows, to *verify* the gateway's number, and to fall back
when the gateway didn't have a price for the model.

The price list is intentionally short. Adding a new model is one line.
Values are conservative estimates roughly matching OpenAI / Anthropic public
list prices as of mid-2026; production users will want to override via the
``LLM_PRICING_OVERRIDES`` env var (a JSON string) or the budget config UI.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# USD cents per 1,000,000 tokens (input + output priced identically here;
# the AIPLLMCall row stores total_tokens so we don't split). This is a
# single-rate simplification — the marketplace reality is asymmetric input
# vs. output pricing, and we should graduate to per-direction pricing when
# ``AIPLLMCall`` starts recording them separately.
MODEL_PRICING: Dict[str, int] = {
    # OpenAI
    "gpt-4o": 500,            # $5.00 / 1M tokens
    "gpt-4o-mini": 15,        # $0.15 / 1M
    "gpt-4-turbo": 1000,      # $10 / 1M
    "gpt-3.5-turbo": 50,      # $0.50 / 1M
    "o1-preview": 1500,       # $15 / 1M
    "o1-mini": 300,           # $3 / 1M
    # Anthropic
    "claude-3-5-sonnet": 300, # $3 / 1M
    "claude-3-5-haiku": 80,   # $0.80 / 1M
    "claude-3-opus": 1500,    # $15 / 1M
    # Qwen / domestic
    "qwen-max": 400,          # $4 / 1M
    "qwen-plus": 80,          # $0.80 / 1M
    "qwen-turbo": 30,         # $0.30 / 1M
    "deepseek-chat": 14,      # $0.14 / 1M
    "glm-4-plus": 700,        # $7 / 1M
    # Generic fallback bucket
    "default": 100,           # $1 / 1M — used when model is unknown
}

# Optional operator override: JSON map of model -> cents per 1M tokens
_OVERRIDES_RAW = os.getenv("LLM_PRICING_OVERRIDES", "")
if _OVERRIDES_RAW:
    try:
        MODEL_PRICING.update({k: int(v) for k, v in json.loads(_OVERRIDES_RAW).items()})
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning(f"Invalid LLM_PRICING_OVERRIDES env var: {exc}")


def lookup(model: str) -> int:
    """Return cents per 1M tokens for the given model, falling back to default."""
    if not model:
        return MODEL_PRICING["default"]
    # Try exact match first, then a loose "family" match (e.g. gpt-4o-2024-08-06
    # should resolve to gpt-4o).
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    for prefix, price in MODEL_PRICING.items():
        if model.startswith(prefix):
            return price
    return MODEL_PRICING["default"]


def compute_cost_cents(model: str, total_tokens: int) -> int:
    """Estimate the cost in USD cents for the given model + token count.

    Returns ``0`` for non-positive token counts to avoid noisy negative
    ledger entries. Rounds **up** so we never under-report.
    """
    if total_tokens <= 0:
        return 0
    rate = lookup(model)
    # rate is cents per 1M tokens; tokens / 1_000_000 * rate
    return max(1, (total_tokens * rate + 999_999) // 1_000_000)


def format_usd(cents: int) -> str:
    """Render cents as a localized USD string. ``$1.23`` for 123."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents / 100:.2f}"
