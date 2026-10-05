"""Models, prices and limits. One place to change what the experiments run on."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    """USD per 1M tokens. Output includes reasoning/thinking tokens."""
    input: float
    cached_input: float
    output: float


@dataclass(frozen=True)
class Model:
    litellm_id: str  # the string LiteLLM routes on
    price: Price


# Prices checked against each provider's pricing page on 2026-10-04.
# tests/test_config.py fails if LiteLLM's own price map disagrees.
MODELS = {
    # OpenAI's GPT-6 family only supports tool calling fully on the Responses API, so these go
    # through LiteLLM's Responses bridge. It still returns chat-completions-shaped messages.
    "gpt-6.1-sol": Model("openai/responses/gpt-6.1-sol", Price(2.00, 0.10, 10.00)),
    "gpt-6-luna": Model("openai/responses/gpt-6-luna", Price(0.10, 0.01, 0.50)),
    # Weekday peak prices; half price outside 01:00-04:00 and 06:00-10:00 UTC. Budgeting at peak.
    "deepseek-flash": Model("deepseek/deepseek-flash", Price(0.30, 0.006, 1.20)),
    # Not in use: Gemini's free tier is too rate-limited for the experiments (5 requests/min).
    # Price rises to 1.50 / 7.50 on 2027-01-01.
    # "gemini-3.8-flash": Model("gemini/gemini-3.8-flash", Price(0.75, 0.075, 3.75)),
    # "claude-sonnet-5-5": Model("anthropic/claude-sonnet-5-5", Price(2.00, 0.20, 10.00)),
}

CUSTOMER_MODEL = "gpt-6-luna"  # plays every simulated customer, whichever agent is being tested

MAX_OUTPUT_TOKENS = 4000  # per model call, including reasoning tokens
MAX_TOOL_STEPS = 8        # model calls per agent turn before we stop the loop
LLM_RETRIES = 5           # retries on rate limits / 5xx, waiting as the provider suggests
