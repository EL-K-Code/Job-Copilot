from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation_dataset import load_benchmark_cases, summarize_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a JobCopilot JSONL benchmark and report coverage."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/job_offers.sample.jsonl"),
    )
    args = parser.parse_args()

    cases = load_benchmark_cases(args.dataset)
    summary = summarize_benchmark(cases)
    summary["dataset"] = str(args.dataset)
    summary["status"] = "valid"
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
