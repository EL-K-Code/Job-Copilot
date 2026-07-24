from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.grounding_review import summarize_grounding_reviews


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            normalized = line.strip()
            if not normalized:
                continue
            try:
                rows.append(json.loads(normalized))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}."
                ) from exc
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize human grounding reviews of generated JobCopilot emails."
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path("evaluation/email_grounding_review.example.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/email_grounding_report.json"),
    )
    args = parser.parse_args()

    summary = summarize_grounding_reviews(load_jsonl(args.annotations))
    report = {
        "task": "generated_email_candidate_claim_grounding",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "annotation_file": str(args.annotations),
        **summary,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "number_of_reviewed_jobs": report["number_of_reviewed_jobs"],
                "number_of_claims": report["number_of_claims"],
                "supported_rate": report["supported_rate"],
                "unsupported_claim_rate": report["unsupported_claim_rate"],
                "ambiguous_rate": report["ambiguous_rate"],
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
