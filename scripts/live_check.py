"""Milestone-1 live check: one agent turn per model with a toy tool, traced to traces/live_check/.

Confirms that each model can call a tool through LiteLLM and answer from the result.
Costs well under $0.01 per model.

    .venv/bin/python scripts/live_check.py [model ...]
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from dutybench.config import MODELS
from dutybench.harness.agent import Agent
from dutybench.harness.tools import Tool, ToolError
from dutybench.harness.trace import Tracer

KEY_FOR = {"openai/": "OPENAI_API_KEY", "gemini/": "GEMINI_API_KEY", "anthropic/": "ANTHROPIC_API_KEY"}
ROOT = Path(__file__).resolve().parent.parent


def next_payment(account_id: str) -> dict:
    if account_id != "LN-4471":
        raise ToolError(f"No account {account_id}. Check the account number.")
    return {"account_id": account_id, "next_payment_date": "2026-10-28", "amount_gbp": 187.40}


TOOL = Tool(
    name="get_next_payment",
    description="Get the date and amount of a loan account's next scheduled payment.",
    parameters={"type": "object", "properties": {"account_id": {"type": "string"}},
                "required": ["account_id"], "additionalProperties": False},
    fn=next_payment,
)


def main():
    load_dotenv(ROOT / ".env")
    for name in sys.argv[1:] or list(MODELS):
        key = next(v for k, v in KEY_FOR.items() if MODELS[name].litellm_id.startswith(k))
        if not os.getenv(key):
            print(f"\n=== {name}: skipped ({key} not set in .env)")
            continue
        path = ROOT / "traces" / "live_check" / f"{name}.jsonl"
        agent = Agent(model=name, tools=[TOOL], tracer=Tracer(path),
                      system_prompt="You are a support agent for a UK lender. Use tools to look things up.")
        reply = agent.respond("Hi, when's my next payment due and how much is it? Account LN-4471.")
        tools_used = [(e["name"], e["output"]) for e in agent.tracer.events if e["type"] == "tool_call"]
        print(f"\n=== {name}\ntool calls: {tools_used}\nreply: {reply}\ntotals: {agent.tracer.totals()}\ntrace: {path.relative_to(ROOT)}")
        agent.tracer.close()


if __name__ == "__main__":
    main()
