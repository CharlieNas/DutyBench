"""Thin wrapper over LiteLLM: one function in, one normalised result out.

Everything else in the harness talks to `complete()` (or a fake with the same signature in tests),
so swapping providers is a config change and the agent loop never sees provider quirks.
"""

import time
from dataclasses import dataclass, field

import litellm

from dutybench.config import LLM_RETRIES, MAX_OUTPUT_TOKENS, MODELS, Price

litellm.suppress_debug_info = True


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string, exactly as the model produced it; validated later


@dataclass
class Usage:
    input_tokens: int = 0
    cached_tokens: int = 0  # subset of input_tokens served from the provider's prompt cache
    output_tokens: int = 0  # includes reasoning tokens


@dataclass
class LLMResult:
    message: dict  # assistant message in chat format, appended to history as-is
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    latency_s: float = 0.0
    cost_usd: float = 0.0
    finish_reason: str | None = None


def cost_usd(price: Price, usage: Usage) -> float:
    uncached = usage.input_tokens - usage.cached_tokens
    return (uncached * price.input + usage.cached_tokens * price.cached_input
            + usage.output_tokens * price.output) / 1e6


def complete(model: str, messages: list[dict], tools: list[dict] | None = None) -> LLMResult:
    """Call `model` (a key in config.MODELS) and normalise the response."""
    spec = MODELS[model]
    start = time.perf_counter()
    response = litellm.completion(
        model=spec.litellm_id,
        messages=messages,
        tools=tools or None,
        max_tokens=MAX_OUTPUT_TOKENS,
        num_retries=LLM_RETRIES,  # LiteLLM backs off on rate limits and transient errors
    )
    latency = time.perf_counter() - start

    choice = response.choices[0]
    # Keep the full message (including provider-specific fields such as Gemini's thought
    # signatures) so it can be sent back unchanged on the next call.
    message = choice.message.model_dump(exclude_none=True)
    tool_calls = [ToolCall(tc.id, tc.function.name, tc.function.arguments or "{}")
                  for tc in (choice.message.tool_calls or [])]

    u = response.usage
    details = getattr(u, "prompt_tokens_details", None)
    usage = Usage(
        input_tokens=u.prompt_tokens or 0,
        cached_tokens=(getattr(details, "cached_tokens", 0) or 0) if details else 0,
        output_tokens=u.completion_tokens or 0,
    )
    return LLMResult(
        message=message,
        text=choice.message.content or "",
        tool_calls=tool_calls,
        usage=usage,
        latency_s=latency,
        cost_usd=cost_usd(spec.price, usage),
        finish_reason=choice.finish_reason,
    )
