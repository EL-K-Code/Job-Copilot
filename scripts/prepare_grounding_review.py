from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_jsonl(path: Path) -> list[dict]:
    cases: list[dict] = []
    with path.open("r", encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            normalized = line.strip()
            if not normalized:
                continue
            try:
                cases.append(json.loads(normalized))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}."
                ) from exc
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run JobCopilot and prepare claim-level human grounding review records."
        )
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/job_offers.v1.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/grounding_review.jsonl"),
    )
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    if args.limit < 1:
        raise ValueError("--limit must be greater than or equal to 1.")

    from app.graph import jobcopilot_graph

    review_records: list[dict] = []
    for case in load_jsonl(args.dataset)[: args.limit]:
        result = jobcopilot_graph.invoke(
            {"job_text": case["job_text"]},
            config={"configurable": {"thread_id": f"grounding-{uuid4()}"}},
        )
        review_records.append(
            {
                "job_id": case["id"],
                "language": case.get("language", "unknown"),
                "email_subject": result["email_draft"]["subject"],
                "email_body": result["email_draft"]["body"],
                "retrieved_memories": result["retrieved_memories"],
                "claims": [],
                "review_status": "pending",
                "review_instructions": (
                    "Split the email into factual candidate claims. For each claim add "
                    "label=supported, unsupported or ambiguous and list supporting_memory_ids."
                ),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file_handle:
        for record in review_records:
            file_handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(json.dumps({"prepared_cases": len(review_records), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
