from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation_sampling import select_review_cases
from app.graph import jobcopilot_graph
from app.memory import load_profile_memories


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
        description=(
            "Generate JobCopilot emails and prepare records for human claim-level "
            "grounding review."
        )
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/job_offers.v1.jsonl"),
    )
    parser.add_argument(
        "--memories",
        type=Path,
        default=Path("data/profile_memories.example.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/email_grounding_review.jsonl"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Generate N review records. Use zero for the full dataset.",
    )
    parser.add_argument(
        "--sampling",
        choices=("head", "stratified"),
        default="stratified",
        help=(
            "Use stratified sampling for small runs so different role families are covered, "
            "or head for the first N dataset rows."
        ),
    )
    args = parser.parse_args()

    if args.limit < 0:
        raise ValueError("--limit cannot be negative.")

    all_cases = load_jsonl(args.dataset)
    cases = select_review_cases(
        all_cases,
        limit=args.limit,
        sampling=args.sampling,
    )

    memories = load_profile_memories(args.memories)
    memory_by_content = {
        str(memory.get("content", "")).strip(): {
            "id": str(memory.get("id", "")).strip(),
            "type": str(memory.get("type", "")).strip(),
            "content": str(memory.get("content", "")).strip(),
        }
        for memory in memories
        if str(memory.get("content", "")).strip()
    }

    review_records: list[dict] = []
    for case in cases:
        result = jobcopilot_graph.invoke({"job_text": case["job_text"]})
        retrieved_records = result.get("retrieved_memory_records", [])
        if not retrieved_records:
            for content in result["retrieved_memories"]:
                record = memory_by_content.get(content)
                retrieved_records.append(
                    record or {"id": "", "type": "unknown", "content": content}
                )

        email_draft = result["email_draft"]
        proposed_claims = email_draft.get("claim_evidence", [])
        selected_memory_ids = [
            memory_id
            for claim in proposed_claims
            for memory_id in claim.get("supporting_memory_ids", [])
        ]
        review_records.append(
            {
                "job_id": case["id"],
                "language": case.get("language", "unknown"),
                "category": case.get("category", "unknown"),
                "sampling_mode": args.sampling,
                "email_subject": email_draft["subject"],
                "email_body": email_draft["body"],
                "composition_variant": email_draft.get("composition_variant", "direct"),
                "selected_memory_ids": selected_memory_ids,
                "retrieved_memories": retrieved_records,
                "proposed_claims": proposed_claims,
                "claims": [],
                "review_status": "pending",
                "review_instructions": (
                    "Review every factual candidate claim in the email. Use proposed_claims "
                    "as a machine-generated starting point, but independently verify claim "
                    "coverage and evidence. Label each reviewed claim supported, unsupported "
                    "or ambiguous, and list only retrieved memory IDs as evidence. Also assess "
                    "whether selected evidence is role-specific rather than merely generic."
                ),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file_handle:
        for record in review_records:
            file_handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "prepared_jobs": len(review_records),
                "categories": sorted(
                    {record["category"] for record in review_records}
                ),
                "sampling_mode": args.sampling,
                "composition_variants": sorted(
                    {record["composition_variant"] for record in review_records}
                ),
                "unique_evidence_selections": len(
                    {
                        tuple(record["selected_memory_ids"])
                        for record in review_records
                    }
                ),
                "proposed_claims": sum(
                    len(record["proposed_claims"]) for record in review_records
                ),
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
