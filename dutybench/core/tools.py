"""Tools: a name, a description, a JSON schema and a Python function.

The same schema is sent to the model and used to validate what the model sends back,
so there is one source of truth for each tool's inputs.
"""

import json
from dataclasses import dataclass
from typing import Any, Callable

from jsonschema import Draft202012Validator


class ToolError(Exception):
    """A business-rule failure (e.g. unknown account). Shown to the model so it can recover."""


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON schema for the arguments object
    fn: Callable[..., Any]

    def spec(self) -> dict:
        """The tool definition in the (OpenAI-style) format LiteLLM expects."""
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters}}


def _describe(error) -> str:
    where = ".".join(str(p) for p in error.absolute_path) or "arguments"
    return f"{where}: {error.message}"


def execute(tools: dict[str, Tool], name: str, raw_arguments: str) -> dict:
    """Run one tool call. Returns {"result": ...} or {"error": "..."}; never raises for model mistakes.

    Bugs in our own tool code (anything other than ToolError) are deliberately NOT caught:
    an evaluation harness should fail loudly rather than blame the model for our bug.
    """
    tool = tools.get(name)
    if tool is None:
        return {"error": f"Unknown tool '{name}'. Available tools: {', '.join(sorted(tools))}."}

    try:
        args = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError as e:
        return {"error": f"Arguments were not valid JSON ({e.msg}). Send a JSON object."}
    if not isinstance(args, dict):
        return {"error": "Arguments must be a JSON object."}

    problems = sorted(Draft202012Validator(tool.parameters).iter_errors(args), key=lambda e: list(e.path))
    if problems:
        return {"error": "Invalid arguments: " + "; ".join(_describe(p) for p in problems)}

    try:
        return {"result": tool.fn(**args)}
    except ToolError as e:
        return {"error": str(e)}
