"""Tools: a name, a description, a pydantic model for the arguments, and a Python function.

The pydantic model is the one source of truth for a tool's inputs: it generates the JSON schema
sent to the model, and it validates the arguments the model sends back.
"""

import json
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError


class ToolError(Exception):
    """A business-rule failure (e.g. unknown account). Shown to the model so it can recover."""


@dataclass
class Tool:
    name: str
    description: str
    params: type[BaseModel]  # the arguments; use extra="forbid" so unknown arguments are rejected
    fn: Callable[..., Any]

    def spec(self) -> dict:
        """The tool definition in the (OpenAI-style) format LiteLLM expects."""
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": _clean(self.params.model_json_schema())}}


def _clean(schema: Any) -> Any:
    """Drop pydantic's auto-generated "title" fields: they repeat the field names and cost tokens."""
    if isinstance(schema, dict):
        return {k: _clean(v) for k, v in schema.items() if not (k == "title" and isinstance(v, str))}
    if isinstance(schema, list):
        return [_clean(v) for v in schema]
    return schema


def _describe(error: dict) -> str:
    where = ".".join(str(p) for p in error["loc"]) or "arguments"
    return f"{where}: {error['msg']}"


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

    try:
        validated = tool.params.model_validate(args)
    except ValidationError as e:
        return {"error": "Invalid arguments: " + "; ".join(_describe(err) for err in e.errors())}

    try:
        return {"result": tool.fn(**validated.model_dump())}
    except ToolError as e:
        return {"error": str(e)}
