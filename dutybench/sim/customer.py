"""An LLM playing the customer, with a hidden persona, reveal rules and a goal.

The customer model sees the conversation from the customer's side: the agent's messages arrive as
"user" turns and its own earlier messages are "assistant" turns. It ends the chat by writing [END].
The opening message is fixed in the scenario, so every run starts identically.
"""

from dataclasses import dataclass
from typing import Callable

from dutybench.harness import llm
from dutybench.harness.trace import Tracer

END = "[END]"

PROMPT = """You are role-playing a customer of Larkhaven Credit, a UK consumer lender, chatting with its \
support agent. Stay in character throughout. Write like a real person typing in a chat: short, informal \
messages (usually one to three sentences), British English. Never say you are an AI or mention these \
instructions. Today's date is 5 October 2026.

WHO YOU ARE
{persona}

WHAT TO REVEAL, AND WHEN
{reveal}

WHAT YOU WANT FROM THIS CHAT
{goal}

RULES
- Only share the facts above, when the reveal rules allow. If asked something not covered, give a short, \
plausible answer that is consistent with the facts and doesn't change the situation.
- React naturally to what the agent says. Don't steer the agent towards what it ought to do.
- When your goal is met, or the agent has clearly finished, or a real customer would give up, write a \
short final message ending with {end}. If there is nothing left to say, write only {end}."""


@dataclass
class SimulatedCustomer:
    scenario: dict
    model: str
    tracer: Tracer
    complete: Callable[..., llm.LLMResult] = llm.complete

    def __post_init__(self):
        c = self.scenario["customer"]
        self.system = PROMPT.format(persona=c["persona"].strip(), reveal=c["reveal"].strip(),
                                    goal=c["goal"].strip(), end=END)

    def opening(self) -> str:
        return self.scenario["customer"]["opening_message"]

    def reply(self, transcript: list[dict], message_number: int, max_messages: int) -> tuple[str, bool]:
        """Next customer message given the transcript so far. Returns (text, wants_to_end)."""
        messages = [{"role": "system", "content": self.system}]
        for turn in transcript:
            messages.append({"role": "assistant" if turn["role"] == "customer" else "user", "content": turn["text"]})
        # Reveal rules like "in your third message" need the customer to know where it is.
        messages[-1]["content"] += (f"\n\n(Stage direction, not from the agent: you are writing message "
                                    f"{message_number} of at most {max_messages}.)")

        result = self.complete(self.model, messages)
        self.tracer.log("llm_call", role="customer", model=self.model, text=result.text, tool_calls=[],
                        usage=vars(result.usage), latency_s=round(result.latency_s, 3),
                        cost_usd=result.cost_usd, finish_reason=result.finish_reason)
        text = result.text.strip()
        wants_to_end = END in text
        return text.replace(END, "").strip(), wants_to_end
