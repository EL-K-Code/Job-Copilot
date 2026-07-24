from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation import evaluate_grounding_labels


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Score grounding-label predictions.")
    parser.add_argument("--gold", type=Path, default=Path("evaluation/grounding_cases.v1.jsonl"))
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/grounding_report.json"))
    args = parser.parse_args()

    gold_rows = load_jsonl(args.gold)
    prediction_rows = load_jsonl(args.predictions)
    gold_by_id = {row["id"]: row["label"] for row in gold_rows}
    prediction_by_id = {row["id"]: row["label"] for row in prediction_rows}

    missing = sorted(set(gold_by_id) - set(prediction_by_id))
    extra = sorted(set(prediction_by_id) - set(gold_by_id))
    if missing or extra:
        raise ValueError(f"Prediction ids do not match gold ids. Missing={missing}; extra={extra}")

    ordered_ids = [row["id"] for row in gold_rows]
    report = evaluate_grounding_labels(
        [prediction_by_id[item_id] for item_id in ordered_ids],
        [gold_by_id[item_id] for item_id in ordered_ids],
    )
    report["number_of_cases"] = len(ordered_ids)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
