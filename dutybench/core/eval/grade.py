"""Grade one conversation: deterministic checks first, then (optionally) the LLM judge."""

import re
from collections.abc import Callable
from pathlib import Path

from dutybench.core.eval import judge as judge_mod
from dutybench.core.eval.checks import CORE_CHECKS, run_checks
from dutybench.core.eval.conversation import Conversation
from dutybench.core.setting import Setting


def rule_ids(rules_file: Path) -> set[str]:
    """Rule ids defined in a setting's rules file (its '### ID' headings)."""
    return set(re.findall(r"^### (\S+)$", rules_file.read_text(), re.MULTILINE))


def all_checks(setting: Setting) -> dict:
    return {**CORE_CHECKS, **setting.checks}


def validate_scenario(scenario: dict, setting: Setting) -> None:
    """Fail early if a scenario refers to a check, criterion or rule that does not exist."""
    known_rules, checks = rule_ids(setting.rules_file), all_checks(setting)
    for spec in scenario.get("checks", []):
        if spec["check"] not in checks:
            raise ValueError(f"{scenario['id']}: unknown check {spec['check']!r}")
        if spec["kind"] not in ("required", "forbidden"):
            raise ValueError(f"{scenario['id']}/{spec['id']}: kind must be required or forbidden")
        if spec["rule"] not in known_rules:
            raise ValueError(
                f"{scenario['id']}/{spec['id']}: rule {spec['rule']!r} is not in {setting.rules_file.name}"
            )
    for cid in scenario.get("judge", []):
        criterion = setting.judge_criteria.get(cid)
        if criterion is None:
            raise ValueError(f"{scenario['id']}: unknown judge criterion {cid!r}")
        if criterion["rule"] not in known_rules:
            raise ValueError(f"judge criterion {cid!r}: rule {criterion['rule']!r} is not in {setting.rules_file.name}")


def grade(
    conv: Conversation, scenario: dict, setting: Setting, use_judge: bool = False, complete: Callable | None = None
) -> dict:
    """Returns one grade record. `passed` means every check passed and, if judged, every criterion
    was marked "pass"."""
    validate_scenario(scenario, setting)
    checks = run_checks(conv, scenario.get("checks", []), all_checks(setting))
    record = {
        "key": conv.key,
        "scenario_id": conv.scenario_id,
        "model": conv.model,
        "condition": conv.condition,
        "run": conv.run,
        "status": conv.status,
        "checks": checks,
        "checks_passed": all(c["passed"] for c in checks),
        "judge": [],
        "judge_cost_usd": 0.0,
    }
    if use_judge:
        kwargs = {"complete": complete} if complete else {}
        record["judge"], record["judge_cost_usd"] = judge_mod.judge(conv, scenario, setting.judge_criteria, **kwargs)
    record["passed"] = record["checks_passed"] and all(j["label"] == "pass" for j in record["judge"])
    return record
