from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation import GROUNDING_LABELS


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            normalized = line.strip()
            if not normalized:
                continue
            try:
                row = json.loads(normalized)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}.") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Line {line_number} of {path} must be a JSON object.")
            rows.append(row)
    return rows


def ensure_unique_ids(rows: list[dict], dataset_name: str) -> None:
    ids = [str(row.get("id", "")).strip() for row in rows]
    if any(not item_id for item_id in ids):
        raise ValueError(f"{dataset_name} contains a missing id.")
    duplicates = [item_id for item_id, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"{dataset_name} contains duplicate ids: {duplicates}")


def validate_job_offers(rows: list[dict]) -> dict:
    if len(rows) != 50:
        raise ValueError(f"Benchmark V1 must contain exactly 50 offers; found {len(rows)}.")
    ensure_unique_ids(rows, "job offers")
    required_expected = {
        "company",
        "role",
        "location",
        "contract_type",
        "start_date",
        "missions_summary",
        "required_skills",
        "preferred_skills",
        "tools_and_stack",
        "domain_focus",
        "key_highlights_for_candidate",
    }
    for row in rows:
        if not str(row.get("job_text", "")).strip():
            raise ValueError(f"{row['id']} has empty job_text.")
        expected = row.get("expected")
        if not isinstance(expected, dict):
            raise ValueError(f"{row['id']} has no expected annotation object.")
        missing = required_expected - set(expected)
        if missing:
            raise ValueError(f"{row['id']} is missing expected fields: {sorted(missing)}")
    category_counts = Counter(str(row.get("category", "Unknown")) for row in rows)
    if len(category_counts) < 10:
        raise ValueError("Benchmark V1 must cover at least 10 role categories.")
    return {"count": len(rows), "categories": dict(sorted(category_counts.items()))}


def validate_retrieval(rows: list[dict], memory_ids: set[str]) -> dict:
    if len(rows) < 20:
        raise ValueError("Retrieval benchmark must contain at least 20 cases.")
    ensure_unique_ids(rows, "retrieval cases")
    for row in rows:
        if not str(row.get("query", "")).strip():
            raise ValueError(f"{row['id']} has an empty retrieval query.")
        relevant = row.get("relevant_memory_ids")
        if not isinstance(relevant, list) or not relevant:
            raise ValueError(f"{row['id']} must contain relevant_memory_ids.")
        unknown = set(relevant) - memory_ids
        if unknown:
            raise ValueError(f"{row['id']} references unknown memory ids: {sorted(unknown)}")
    return {"count": len(rows)}


def validate_grounding(rows: list[dict], memory_ids: set[str]) -> dict:
    if len(rows) < 20:
        raise ValueError("Grounding benchmark must contain at least 20 cases.")
    ensure_unique_ids(rows, "grounding cases")
    labels = Counter()
    for row in rows:
        if not str(row.get("claim", "")).strip():
            raise ValueError(f"{row['id']} has an empty claim.")
        label = row.get("label")
        if label not in GROUNDING_LABELS:
            raise ValueError(f"{row['id']} has invalid label: {label}")
        labels[label] += 1
        evidence = row.get("evidence_ids", [])
        if not isinstance(evidence, list):
            raise ValueError(f"{row['id']} evidence_ids must be a list.")
        unknown = set(evidence) - memory_ids
        if unknown:
            raise ValueError(f"{row['id']} references unknown evidence ids: {sorted(unknown)}")
    if set(labels) != set(GROUNDING_LABELS):
        raise ValueError("Grounding cases must include supported, unsupported and ambiguous labels.")
    return {"count": len(rows), "labels": dict(labels)}


def main() -> None:
    evaluation_dir = PROJECT_ROOT / "evaluation"
    memories = json.loads(
        (PROJECT_ROOT / "data" / "profile_memories.example.json").read_text(encoding="utf-8")
    )
    memory_ids = {str(item["id"]) for item in memories}

    report = {
        "job_offers": validate_job_offers(load_jsonl(evaluation_dir / "job_offers.v1.jsonl")),
        "retrieval": validate_retrieval(
            load_jsonl(evaluation_dir / "retrieval_cases.v1.jsonl"), memory_ids
        ),
        "grounding": validate_grounding(
            load_jsonl(evaluation_dir / "grounding_cases.v1.jsonl"), memory_ids
        ),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
