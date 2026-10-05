"""The agent loop.

    customer message
          │
          ▼
    ┌─► call model (history + tool definitions)
    │     │
    │     ├─ text reply, no tool calls ──► return reply to the customer
    │     │
    │     └─ tool calls ──► validate + run each ──► append results to history
    │                                                     │
    └─────────────────────────────────────────────────────┘
          (at most MAX_TOOL_STEPS model calls per customer message)

The agent holds the conversation history; the caller (simulator, demo, test) supplies customer
messages one at a time. `complete` is injectable so tests can script the model's behaviour.
"""

import json
from dataclasses import dataclass, field
from typing import Callable

from dutybench.config import MAX_TOOL_STEPS
from dutybench.harness import llm
from dutybench.harness.tools import Tool, execute
from dutybench.harness.trace import Tracer

STEP_LIMIT_REPLY = ("I'm sorry, I wasn't able to complete that just now. "
                    "I'm passing your conversation to a colleague who will follow up with you.")


def build_system_message(system_prompt: str, policy_doc: str | None = None) -> dict:
    """System prompt first, then the policy document if this is the 'grounded' condition.
    Both are fixed for the whole conversation, so the provider can cache this prefix."""
    content = system_prompt
    if policy_doc:
        content += "\n\n# Policy you must follow\n\n" + policy_doc
    return {"role": "system", "content": content}


@dataclass
class Agent:
    model: str
    system_prompt: str
    tools: list[Tool]
    tracer: Tracer
    policy_doc: str | None = None
    max_steps: int = MAX_TOOL_STEPS
    complete: Callable[..., llm.LLMResult] = llm.complete
    messages: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self._tools = {t.name: t for t in self.tools}
        self._specs = [t.spec() for t in self.tools]
        self.messages = [build_system_message(self.system_prompt, self.policy_doc)]

    def respond(self, customer_text: str) -> str:
        """Handle one customer message and return the agent's reply."""
        self.messages.append({"role": "user", "content": customer_text})
        self.tracer.log("customer_msg", text=customer_text)

        for step in range(1, self.max_steps + 1):
            result = self.complete(self.model, self.messages, self._specs)
            self.messages.append(result.message)
            self.tracer.log(
                "llm_call", role="agent", model=self.model, step=step,
                n_messages=len(self.messages) - 1, text=result.text,
                tool_calls=[{"id": c.id, "name": c.name, "arguments": c.arguments} for c in result.tool_calls],
                usage=vars(result.usage), latency_s=round(result.latency_s, 3),
                cost_usd=result.cost_usd, finish_reason=result.finish_reason,
            )

            if not result.tool_calls:
                self.tracer.log("agent_reply", text=result.text)
                return result.text

            for call in result.tool_calls:
                output = execute(self._tools, call.name, call.arguments)
                self.tracer.log("tool_call", id=call.id, name=call.name,
                                arguments=call.arguments, output=output)
                self.messages.append({"role": "tool", "tool_call_id": call.id,
                                      "content": json.dumps(output, default=str)})

        # The model kept calling tools without ever answering: stop, hand over, and record it.
        self.tracer.log("step_limit", max_steps=self.max_steps)
        self.messages.append({"role": "assistant", "content": STEP_LIMIT_REPLY})
        self.tracer.log("agent_reply", text=STEP_LIMIT_REPLY, forced=True)
        return STEP_LIMIT_REPLY
