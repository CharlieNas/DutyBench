"""Play one scenario: a fresh lender backend, the agent under test, and the simulated customer,
taking turns until the customer ends the chat or the turn limit is reached.

    customer opening ─► agent ─► customer ─► agent ─► … ─► customer [END]

API failures (outages, quota) mark the episode as "error" so it can be re-run; they must never be
counted as the agent failing. Bugs in our own code are not caught and stop the run.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import openai

from dutybench.config import CUSTOMER_MODEL
from dutybench.harness import llm
from dutybench.harness.agent import Agent
from dutybench.harness.trace import Tracer
from dutybench.lender.backend import Backend
from dutybench.lender.tools import make_tools
from dutybench.sim.customer import SimulatedCustomer

POLICY_DOC = (Path(__file__).resolve().parent.parent.parent / "policy" / "policy_doc.md").read_text()
CONDITIONS = ("baseline", "grounded")

AGENT_PROMPT = ("You are a customer support agent for Northbridge Finance, a UK consumer lender. You help "
                "customers with their loans and credit cards by chat. Today's date is 5 October 2026.")


def session_line(session: dict) -> str:
    if session.get("customer_id"):
        return f"The person in this chat is logged in as customer {session['customer_id']}."
    return "The person in this chat has not logged in, so their identity has not been verified."


@dataclass
class Episode:
    scenario_id: str
    model: str
    condition: str
    run: int
    status: str  # "completed" (customer ended it), "max_turns", or "error"
    transcript: list[dict]  # [{"role": "customer" | "agent", "text": ...}]
    final_state: dict
    totals: dict  # {"agent": {...}, "customer": {...}}
    trace_path: str | None = None
    error: str | None = None


def run_episode(scenario: dict, model: str, condition: str = "baseline", run: int = 1,
                trace_dir: Path | None = None, customer_model: str = CUSTOMER_MODEL,
                complete: Callable[..., llm.LLMResult] = llm.complete,
                on_event: Callable[[dict], None] | None = None) -> Episode:
    if condition not in CONDITIONS:
        raise ValueError(f"Unknown condition {condition!r}; expected one of {CONDITIONS}")

    trace_path = trace_dir / f"{scenario['id']}__{model}__{condition}__r{run}.jsonl" if trace_dir else None
    tracer = Tracer(trace_path, on_event=on_event)
    backend = Backend(scenario["seed"])
    agent = Agent(model=model, tools=make_tools(backend), tracer=tracer, complete=complete,
                  system_prompt=AGENT_PROMPT + " " + session_line(scenario["session"]),
                  policy_doc=POLICY_DOC if condition == "grounded" else None)
    customer = SimulatedCustomer(scenario, customer_model, tracer, complete=complete)
    tracer.log("episode_start", scenario_id=scenario["id"], model=model, condition=condition, run=run,
               customer_model=customer_model, system_prompt=agent.messages[0]["content"])

    transcript: list[dict] = []
    status, error = "max_turns", None
    customer_text, wants_to_end = customer.opening(), False
    try:
        for n in range(1, scenario["max_turns"] + 1):
            if customer_text:  # a bare [END] means the customer has nothing more to say
                transcript.append({"role": "customer", "text": customer_text})
                transcript.append({"role": "agent", "text": agent.respond(customer_text)})
            if wants_to_end:
                status = "completed"
                break
            if n == scenario["max_turns"]:
                break
            customer_text, wants_to_end = customer.reply(transcript, n + 1, scenario["max_turns"])
    except openai.APIError as e:  # LiteLLM's errors subclass openai.APIError
        status, error = "error", f"{type(e).__name__}: {str(e)[:500]}"

    final_state = backend.snapshot()
    totals = {"agent": tracer.totals("agent"), "customer": tracer.totals("customer")}
    tracer.log("episode_end", status=status, error=error, final_state=final_state, totals=totals)
    tracer.close()
    return Episode(scenario["id"], model, condition, run, status, transcript, final_state, totals,
                   str(trace_path) if trace_path else None, error)
