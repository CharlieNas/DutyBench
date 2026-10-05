"""A scripted stand-in for llm.complete, so the agent loop can be tested with no API calls."""

import json

from dutybench.harness.llm import LLMResult, ToolCall, Usage


def reply(text: str) -> LLMResult:
    return LLMResult(message={"role": "assistant", "content": text}, text=text,
                     usage=Usage(100, 0, 20), cost_usd=0.001)


def call(name: str, arguments: dict | str, id: str = "call_1") -> LLMResult:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    message = {"role": "assistant", "tool_calls": [
        {"id": id, "type": "function", "function": {"name": name, "arguments": raw}}]}
    return LLMResult(message=message, text="", tool_calls=[ToolCall(id, name, raw)],
                     usage=Usage(100, 0, 20), cost_usd=0.001)


class FakeLLM:
    """Returns the scripted results in order and records what it was sent."""

    def __init__(self, *results: LLMResult):
        self.results = list(results)
        self.requests: list[list[dict]] = []

    def __call__(self, model, messages, tools=None):
        self.requests.append([dict(m) for m in messages])
        return self.results.pop(0)
