"""Grade every conversation trace in a folder and print the results.

    .venv/bin/python scripts/grade.py traces/play            # deterministic checks only (free)
    .venv/bin/python scripts/grade.py traces/play --judge    # also run the LLM judge (costs a little)

Writes results/grades_<folder>.jsonl, one grade record per conversation.
"""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from dutybench.core.eval.conversation import Conversation
from dutybench.core.eval.grade import grade
from dutybench.core.scenarios import load_scenarios
from dutybench.settings import get_setting

ROOT = Path(__file__).resolve().parent.parent
MARK = {True: "PASS", False: "FAIL"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("folder", type=Path)
    p.add_argument("--judge", action="store_true")
    p.add_argument("--details", action="store_true", help="print the evidence for every check")
    args = p.parse_args()
    load_dotenv(ROOT / ".env")

    records, judge_cost, scenarios = [], 0.0, {}
    for path in sorted(args.folder.glob("*.jsonl")):
        conv = Conversation.from_trace(path)
        setting = get_setting(conv.setting)
        scenarios.update({s["id"]: s for s in load_scenarios(setting.scenario_dir)})
        if conv.status == "error" or conv.scenario_id not in scenarios:
            print(f"skipped {path.name} ({conv.status})")
            continue
        record = grade(conv, scenarios[conv.scenario_id], setting, use_judge=args.judge)
        judge_cost += record["judge_cost_usd"]
        records.append(record)

    for sid in sorted({r["scenario_id"] for r in records}):
        rows = [r for r in records if r["scenario_id"] == sid]
        columns = [c["id"] for c in rows[0]["checks"]] + [j["id"] for j in rows[0]["judge"]]
        print(f"\n{sid} {scenarios[sid]['title']}")
        print(f"  {'model':16} {'condition':9} " + " ".join(f"{c[:22]:22}" for c in columns) + " overall")
        for r in sorted(rows, key=lambda r: (r["model"], r["condition"], r["run"])):
            cells = [MARK[c["passed"]] for c in r["checks"]] + [j["label"] for j in r["judge"]]
            print(
                f"  {r['model']:16} {r['condition']:9} " + " ".join(f"{c:22}" for c in cells) + f" {MARK[r['passed']]}"
            )
            if args.details:
                for c in r["checks"]:
                    print(f"      {MARK[c['passed']]} {c['id']} [{c['rule']}]: {c['evidence'][:200]}")
                for j in r["judge"]:
                    quote = f' "{j["quote"]}"' + ("" if j["quote_found"] else " (QUOTE NOT FOUND IN TRANSCRIPT)")
                    print(f"      {j['label']} {j['id']} [{j['rule']}]: {j['reason']}{quote}")

    out = ROOT / "results" / f"grades_{args.folder.name}.jsonl"
    out.parent.mkdir(exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    print(
        f"\n{len(records)} conversations graded -> {out.relative_to(ROOT)}"
        + (f"   judge cost ${judge_cost:.4f}" if args.judge else "")
    )


if __name__ == "__main__":
    main()
