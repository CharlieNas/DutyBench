"""Load scenario YAML files from dutybench/scenarios/."""

from pathlib import Path

import yaml

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"
REQUIRED_KEYS = {"id", "title", "session", "seed", "customer", "max_turns"}
REQUIRED_CUSTOMER_KEYS = {"opening_message", "persona", "reveal", "goal"}


def load_scenario(path: Path) -> dict:
    scenario = yaml.safe_load(path.read_text())
    missing = (REQUIRED_KEYS - scenario.keys()) | (REQUIRED_CUSTOMER_KEYS - scenario.get("customer", {}).keys())
    if missing:
        raise ValueError(f"{path.name} is missing: {', '.join(sorted(missing))}")
    if not path.name.startswith(scenario["id"] + "_"):
        raise ValueError(f"{path.name}: file name should start with its id {scenario['id']}_")
    return scenario


def load_scenarios(ids: list[str] | None = None) -> list[dict]:
    """All scenarios in id order, or only the given ids (e.g. ["S01", "S08"])."""
    scenarios = [load_scenario(p) for p in sorted(SCENARIO_DIR.glob("S*.yaml"))]
    if ids:
        unknown = set(ids) - {s["id"] for s in scenarios}
        if unknown:
            raise ValueError(f"Unknown scenario ids: {', '.join(sorted(unknown))}")
        scenarios = [s for s in scenarios if s["id"] in ids]
    return scenarios
