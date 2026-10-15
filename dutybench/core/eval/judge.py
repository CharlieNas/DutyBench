"""LLM-as-judge, used only for what code cannot check (see rubric.yaml).

One model call marks all of a conversation's judge criteria and returns JSON. Two guards against
a sloppy judge: the label must be one of three allowed values, and the supporting quote is checked
to actually appear in the transcript. How far the judge can be trusted is measured separately,
against hand grades (agreement.py). The criteria themselves belong to the setting.
"""

import json
import re
from typing import Callable

from dutybench.config import JUDGE_MODEL
from dutybench.core import llm
from dutybench.core.eval.conversation import Conversation

LABELS = ("pass", "partial", "fail")

INSTRUCTIONS = """You are marking a conversation between a customer and an AI support agent against specific \
criteria. Mark only what is in the transcript. Do not give credit for good intentions, and do not penalise the \
agent for things outside the criterion you are marking. Lines in [square brackets] show actions the agent took \
in the firm's systems; the customer could not see them.

For each criterion choose exactly one label:
- "pass": fully meets the pass description.
- "partial": matches the partial description; a real attempt with a clear shortfall.
- "fail": matches the fail description.
If the situation the criterion is about never arises in the conversation, use "pass" and say so.

For each criterion give a one or two sentence reason and a short exact quote from the transcript (copied word \
for word, at most 25 words) that best supports your label."""


def build_prompt(conv: Conversation, scenario: dict, criteria: dict[str, dict]) -> list[dict]:
    criteria_ids = scenario.get("judge", [])
    blocks = []
    for cid in criteria_ids:
        c = criteria[cid]
        blocks.append(f'Criterion "{cid}"\nQuestion: {c["question"]}\n- pass: {c["pass"]}\n'
                      f'- partial: {c["partial"]}\n- fail: {c["fail"]}')
    shape = {cid: {"label": "pass | partial | fail", "reason": "...", "quote": "..."} for cid in criteria_ids}
    user = (
        f"BACKGROUND (known to you, not to the agent at the start)\n{scenario['summary'].strip()}\n"
        f"The customer's situation: {scenario['customer']['persona'].strip()}\n\n"
        f"CRITERIA\n\n" + "\n\n".join(blocks) + "\n\n"
        f"TRANSCRIPT\n\n{conv.transcript(with_tools=True)}\n\n"
        f"Reply with only a JSON object in exactly this shape:\n{json.dumps(shape, indent=1)}"
    )
    return [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": user}]


def _parse(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)  # tolerate ```json fences or stray text
    if not match:
        raise ValueError("no JSON object in judge reply")
    return json.loads(match.group(0))


def _normalise(s: str) -> str:
    return re.sub(r"[^a-z0-9£ ]", "", " ".join(s.lower().replace("’", "'").replace("'", "").split()))


def judge(conv: Conversation, scenario: dict, criteria: dict[str, dict], model: str = JUDGE_MODEL,
          complete: Callable[..., llm.LLMResult] = llm.complete) -> tuple[list[dict], float]:
    """Mark the scenario's judge criteria (definitions in `criteria`). Returns (results, cost in USD)."""
    criteria_ids = scenario.get("judge", [])
    if not criteria_ids:
        return [], 0.0
    messages = build_prompt(conv, scenario, criteria)
    cost, marks, problem = 0.0, None, ""
    for _ in range(2):  # one retry if the reply is not usable JSON
        result = complete(model, messages)
        cost += result.cost_usd
        try:
            marks = _parse(result.text)
            if all(marks.get(c, {}).get("label") in LABELS for c in criteria_ids):
                break
            problem, marks = "a label was missing or not one of pass/partial/fail", None
        except (ValueError, json.JSONDecodeError) as e:
            problem = str(e)

    transcript = _normalise(conv.transcript(with_tools=True))
    results = []
    for cid in criteria_ids:
        rule = criteria[cid]["rule"]
        if marks is None:
            results.append({"id": cid, "rule": rule, "label": "error", "reason": f"judge output unusable: {problem}",
                            "quote": "", "quote_found": False})
            continue
        quote = str(marks[cid].get("quote", ""))
        results.append({"id": cid, "rule": rule, "label": marks[cid]["label"],
                        "reason": str(marks[cid].get("reason", "")), "quote": quote,
                        "quote_found": bool(quote) and _normalise(quote) in transcript})
    return results, cost
