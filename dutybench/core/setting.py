"""The contract between the core and a setting (a domain such as lending).

The core (agent loop, tools, simulator, runner, evaluation) knows nothing about any domain. A setting
supplies everything domain-specific in one Setting object: its prompts, its backend and tools, its
scenarios, the rules its checks cite, its extra checks and its judge criteria. Adding a setting means
writing one of these; tests/test_structure.py fails if core code ever imports a setting.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from dutybench.core.tools import Tool


class Backend(Protocol):
    """A setting's fake system of record, rebuilt from a scenario's seed for every conversation."""

    def snapshot(self) -> dict:
        """The full state, saved at the end of a conversation so checks can inspect it."""
        ...


# A deterministic check: (conversation, **scenario args) -> (passed, evidence).
Check = Callable[..., tuple[bool, str]]


@dataclass(frozen=True)
class Setting:
    name: str
    agent_prompt: str                       # the agent's job description (system prompt)
    customer_context: str                   # who the simulated customer is and who they are talking to
    policy_doc: str                         # added to the agent's prompt in the "grounded" condition
    session_line: Callable[[dict], str]     # tells the agent who it is talking to, from scenario["session"]
    make_backend: Callable[[dict], Backend]  # scenario seed -> fresh backend
    make_tools: Callable[[Any], list[Tool]]  # backend -> the tools the agent may call
    scenario_dir: Path
    rules_file: Path                        # markdown with '### RULE-ID' headings
    checks: dict[str, Check] = field(default_factory=dict)        # extra checks, beyond the core ones
    judge_criteria: dict[str, dict] = field(default_factory=dict)  # id -> {rule, question, pass, partial, fail}
