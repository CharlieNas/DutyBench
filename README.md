# DutyBench

[![tests](https://github.com/CharlieNas/DutyBench/actions/workflows/tests.yml/badge.svg)](https://github.com/CharlieNas/DutyBench/actions/workflows/tests.yml)

**Does a customer-support AI agent follow UK consumer-credit rules?**

DutyBench puts a tool-using support agent for a fictional UK lender ("Larkhaven Credit", not a real firm) into multi-turn conversations with simulated customers: someone recently bereaved, someone who has lost their job, someone asking for an unaffordable payment plan, a complaint, a "safe account" scam. It then grades what the agent actually *did* (its tool calls and the lender's backend state), not just what it said, against FCA rules: Consumer Duty, CONC 7 (arrears and forbearance) and complaints handling.

The agent harness is written from scratch, with no agent frameworks. LiteLLM is used only to call the models, so they can be swapped by name.

## Status: work in progress

DutyBench is a small toolkit for building and testing reliable AI agents. The **core** (agent loop, tools, tracing, simulated customers, evaluation) is general; **settings** plug a domain into it. Lending is the first setting.

- [x] Probe study to choose the domain ([`probes/`](probes/))
- [x] Core/setting split, pydantic tool schemas, ruff, CI on Python 3.12
- [ ] Lending setting on a seeded SQLite database, with the full tool set
- [ ] Response cache, hard cost cap and run records
- [ ] Replay view for conversation traces
- [ ] Policy engine: guardrails enforced in code
- [ ] 40 scenarios, including adversarial ones
- [ ] One-command evaluation suite and report, with judge vs human agreement
- [ ] Write-up with results

## Run the tests

The tests use a scripted fake model, so they need no API keys and cost nothing.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

> **Inspired by FCA rules, not legal advice, fake data only.** Every rule used for grading cites its source, with a note on how confident the reading is. The lender, its customers and all figures are invented.
