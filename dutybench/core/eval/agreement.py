"""How far can the LLM judge be trusted? Compare its labels with a human's on the same conversations.

Workflow:
  1. export_for_hand_grading(...) writes transcripts.md and labels.csv for a sample of conversations.
     The export is blind: conversations get neutral ids (C01, C02, ...) and the model, condition and
     the judge's own labels are left out, so the human is not influenced by them.
  2. The human fills in the human_label column (pass / partial / fail).
  3. agreement(...) reports, per criterion, the share of identical labels and Cohen's kappa
     (agreement corrected for the amount expected by chance).
"""

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from dutybench.core.eval.conversation import Conversation
from dutybench.core.eval.judge import LABELS


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Kappa for two raters' labels. None if it is undefined (no pairs, or chance agreement is 100%)."""
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    count_a, count_b = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(count_a[label] * count_b[label] for label in LABELS) / (n * n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def export_for_hand_grading(grades: list[dict], conversations: dict[str, Conversation], criteria: dict[str, dict],
                            out_dir: Path, n: int = 20, seed: int = 0) -> Path:
    """Sample up to n judged conversations and write the blind hand-grading pack."""
    judged = [g for g in grades if g["judge"]]
    sample = random.Random(seed).sample(judged, min(n, len(judged)))
    out_dir.mkdir(parents=True, exist_ok=True)
    key, pages, rows = {}, [], []
    for i, g in enumerate(sample, 1):
        cid = f"C{i:02d}"
        key[cid] = g["key"]
        pages.append(f"# {cid}\n\n{conversations[g['key']].transcript(with_tools=True)}\n")
        for j in g["judge"]:
            c = criteria[j["id"]]
            rows.append({"conversation": cid, "criterion": j["id"], "question": c["question"],
                         "pass_means": c["pass"], "partial_means": c["partial"], "fail_means": c["fail"],
                         "human_label": ""})
    (out_dir / "transcripts.md").write_text("\n---\n\n".join(pages))
    (out_dir / "key.json").write_text(json.dumps(key, indent=1))  # do not open until grading is done
    with (out_dir / "labels.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return out_dir


def agreement(labels_csv: Path, key_json: Path, grades: list[dict]) -> dict:
    """Per-criterion and overall agreement between the human labels and the judge."""
    key = json.loads(key_json.read_text())
    judge_labels = {(g["key"], j["id"]): j["label"] for g in grades for j in g["judge"]}
    pairs = defaultdict(list)
    with labels_csv.open() as f:
        for row in csv.DictReader(f):
            human = row["human_label"].strip().lower()
            if human not in LABELS:
                continue  # not graded yet
            judge_label = judge_labels.get((key[row["conversation"]], row["criterion"]))
            if judge_label in LABELS:
                pairs[row["criterion"]].append((human, judge_label))
    report = {}
    for name, ps in {**pairs, "overall": [p for ps in pairs.values() for p in ps]}.items():
        report[name] = {"n": len(ps),
                        "agreement": round(sum(a == b for a, b in ps) / len(ps), 3) if ps else None,
                        "kappa": None if (k := cohens_kappa(ps)) is None else round(k, 3)}
    return report
