# DutyBench

**Does a customer-support AI agent follow UK consumer-credit rules?**

DutyBench puts a tool-using support agent for a fictional UK lender into multi-turn conversations with simulated customers: someone recently bereaved, someone who has lost their job, someone asking for an unaffordable payment plan, a complaint, a "safe account" scam. It then grades what the agent actually *did* (its tool calls and the lender's backend state), not just what it said, against FCA rules: Consumer Duty, CONC 7 (arrears and forbearance) and complaints handling.

The agent harness is written from scratch, with no agent frameworks. LiteLLM is used only to call the models, so they can be swapped by name.

## Status: work in progress

- [x] Probe study to choose the domain ([`probes/`](probes/))
- [x] Agent harness: tool loop, schema-validated tools, JSONL tracing, cost tracking
- [ ] Simulated lender (in-memory backend + 9 tools)
- [ ] Multi-turn scenarios with simulated customers
- [ ] Grading: deterministic checks + LLM judge, each tied to a cited rule
- [ ] Experiments: baseline vs grounded vs a harness improvement, across models
- [ ] Web demo
- [ ] Full write-up with results

## Run the tests

The tests use a scripted fake model, so they need no API keys and cost nothing.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

All data in this project is synthetic.
