from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation import summarize_grounding_annotations


def load_claims(path: Path) -> list[dict]:
    claims: list[dict] = []
    with path.open("r", encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            normalized = line.strip()
            if not normalized:
                continue
            try:
                record = json.loads(normalized)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}."
                ) from exc

            for claim in record.get("claims", []):
                claims.append(
                    {
                        "job_id": record.get("job_id", ""),
                        "claim": claim.get("claim", ""),
                        "label": claim.get("label", ""),
                        "supporting_memory_ids": claim.get(
                            "supporting_memory_ids", []
                        ),
                        "reviewer": claim.get("reviewer", ""),
                    }
                )
    return claims


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize human claim-grounding annotations."
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path("evaluation/grounding_annotations.example.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/grounding_report.json"),
    )
    args = parser.parse_args()

    claims = load_claims(args.annotations)
    summary = summarize_grounding_annotations(claims)
    report = {
        "task": "candidate_claim_grounding",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "annotation_file": str(args.annotations),
        **summary,
        "claims": claims,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({**summary, "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
