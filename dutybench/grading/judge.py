"""LLM-as-judge, used only for what code cannot check (see rubric.yaml).

One model call marks all of a conversation's judge criteria and returns JSON. Two guards against
a sloppy judge: the label must be one of three allowed values, and the supporting quote is checked
to actually appear in the transcript. How far the judge can be trusted is measured separately,
against hand grades (agreement.py).
"""

import json
import re
from pathlib import Path
from typing import Callable

import yaml

from dutybench.config import JUDGE_MODEL
from dutybench.grading.conversation import Conversation
from dutybench.harness import llm

RUBRIC = yaml.safe_load((Path(__file__).parent / "rubric.yaml").read_text())
LABELS = ("pass", "partial", "fail")


def build_prompt(conv: Conversation, scenario: dict, criteria_ids: list[str]) -> list[dict]:
    blocks = []
    for cid in criteria_ids:
        c = RUBRIC["criteria"][cid]
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
    return [{"role": "system", "content": RUBRIC["instructions"]}, {"role": "user", "content": user}]


def _parse(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)  # tolerate ```json fences or stray text
    if not match:
        raise ValueError("no JSON object in judge reply")
    return json.loads(match.group(0))


def _normalise(s: str) -> str:
    return re.sub(r"[^a-z0-9£ ]", "", " ".join(s.lower().replace("’", "'").replace("'", "").split()))


def judge(conv: Conversation, scenario: dict, model: str = JUDGE_MODEL,
          complete: Callable[..., llm.LLMResult] = llm.complete) -> tuple[list[dict], float]:
    """Mark the scenario's judge criteria. Returns (results, cost in USD)."""
    criteria_ids = scenario.get("judge", [])
    if not criteria_ids:
        return [], 0.0
    messages = build_prompt(conv, scenario, criteria_ids)
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
        rule = RUBRIC["criteria"][cid]["rule"]
        if marks is None:
            results.append({"id": cid, "rule": rule, "label": "error", "reason": f"judge output unusable: {problem}",
                            "quote": "", "quote_found": False})
            continue
        quote = str(marks[cid].get("quote", ""))
        results.append({"id": cid, "rule": rule, "label": marks[cid]["label"],
                        "reason": str(marks[cid].get("reason", "")), "quote": quote,
                        "quote_found": bool(quote) and _normalise(quote) in transcript})
    return results, cost
