"""Play scenarios against models and print readable transcripts with the agent's tool calls.

    .venv/bin/python scripts/play.py --scenarios S01 S08 --models gpt-6-luna --conditions baseline

Traces go to traces/play/. This is for looking at conversations; experiments/run.py does the
systematic runs.
"""

import argparse
import json
import textwrap
from pathlib import Path

from dotenv import load_dotenv

from dutybench.config import MODELS
from dutybench.sim.runner import CONDITIONS, run_episode
from dutybench.sim.scenarios import load_scenarios

ROOT = Path(__file__).resolve().parent.parent


def show(event: dict):
    wrap = lambda s: textwrap.indent(textwrap.fill(s, 110, replace_whitespace=False), "    ")
    if event["type"] == "customer_msg":
        print(f"\n  CUSTOMER:\n{wrap(event['text'])}")
    elif event["type"] == "tool_call":
        out = event["output"]
        status = f"ERROR: {out['error']}" if "error" in out else "ok"
        print(f"\n    → {event['name']}({event['arguments']})  [{status}]")
    elif event["type"] == "agent_reply":
        print(f"\n  AGENT:\n{wrap(event['text'])}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scenarios", nargs="+")
    p.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    p.add_argument("--conditions", nargs="+", default=["baseline"], choices=CONDITIONS)
    args = p.parse_args()
    load_dotenv(ROOT / ".env")

    total = 0.0
    for scenario in load_scenarios(args.scenarios):
        for model in args.models:
            for condition in args.conditions:
                print(f"\n{'=' * 100}\n{scenario['id']} {scenario['title']} | {model} | {condition}")
                ep = run_episode(scenario, model, condition, trace_dir=ROOT / "traces" / "play", on_event=show)
                cost = ep.totals["agent"]["cost_usd"] + ep.totals["customer"]["cost_usd"]
                total += cost
                print(f"\n  [{ep.status}{': ' + ep.error if ep.error else ''}] "
                      f"{len(ep.transcript) // 2} customer messages, agent ${ep.totals['agent']['cost_usd']:.4f}, "
                      f"customer ${ep.totals['customer']['cost_usd']:.4f}, "
                      f"agent model time {ep.totals['agent']['llm_latency_s']:.0f}s")
                created = {k: v for k, v in ep.final_state.items() if isinstance(v, list) and v}
                print(f"  backend records created: {json.dumps(created)}")
    print(f"\nTotal cost: ${total:.4f}")


if __name__ == "__main__":
    main()
