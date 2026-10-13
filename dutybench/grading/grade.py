"""Grade one conversation: deterministic checks first, then (optionally) the LLM judge."""

import re
from pathlib import Path
from typing import Callable

from dutybench.grading import judge as judge_mod
from dutybench.grading.checks import CHECKS, run_checks
from dutybench.grading.conversation import Conversation

RULES_FILE = Path(__file__).resolve().parent.parent.parent / "policy" / "rules.md"


def rule_ids() -> set[str]:
    """Rule ids defined in policy/rules.md (its '### ID' headings)."""
    return set(re.findall(r"^### (\S+)$", RULES_FILE.read_text(), re.MULTILINE))


def validate_scenario(scenario: dict) -> None:
    """Fail early if a scenario refers to a check, criterion or rule that does not exist."""
    known_rules = rule_ids()
    for spec in scenario.get("checks", []):
        if spec["check"] not in CHECKS:
            raise ValueError(f"{scenario['id']}: unknown check {spec['check']!r}")
        if spec["kind"] not in ("required", "forbidden"):
            raise ValueError(f"{scenario['id']}/{spec['id']}: kind must be required or forbidden")
        if spec["rule"] not in known_rules:
            raise ValueError(f"{scenario['id']}/{spec['id']}: rule {spec['rule']!r} is not in policy/rules.md")
    for cid in scenario.get("judge", []):
        criterion = judge_mod.RUBRIC["criteria"].get(cid)
        if criterion is None:
            raise ValueError(f"{scenario['id']}: unknown judge criterion {cid!r}")
        if criterion["rule"] not in known_rules:
            raise ValueError(f"rubric criterion {cid!r}: rule {criterion['rule']!r} is not in policy/rules.md")


def grade(conv: Conversation, scenario: dict, use_judge: bool = False,
          complete: Callable | None = None) -> dict:
    """Returns one grade record. `passed` means every check passed and, if judged, every criterion
    was marked "pass"."""
    validate_scenario(scenario)
    checks = run_checks(conv, scenario.get("checks", []))
    record = {"key": conv.key, "scenario_id": conv.scenario_id, "model": conv.model,
              "condition": conv.condition, "run": conv.run, "status": conv.status,
              "checks": checks, "checks_passed": all(c["passed"] for c in checks),
              "judge": [], "judge_cost_usd": 0.0}
    if use_judge:
        kwargs = {"complete": complete} if complete else {}
        record["judge"], record["judge_cost_usd"] = judge_mod.judge(conv, scenario, **kwargs)
    record["passed"] = record["checks_passed"] and all(j["label"] == "pass" for j in record["judge"])
    return record
