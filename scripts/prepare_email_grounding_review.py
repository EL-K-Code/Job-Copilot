from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.email_composer import (
    compose_grounded_email_draft,
    deterministic_fallback_selection,
)
from app.evaluation_sampling import select_review_cases
from app.graph import (
    EMAIL_RETRIEVAL_K,
    build_retrieval_query,
    jobcopilot_graph,
    memory_documents_to_records,
)
from app.memory import load_profile_memories, retrieve_profile_context
from app.schemas import JobAnalysis


ExecutionMode = str


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            normalized = line.strip()
            if not normalized:
                continue
            try:
                row = json.loads(normalized)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}."
                ) from exc
            if not isinstance(row, dict):
                raise ValueError(f"Line {line_number} of {path} must be a JSON object.")
            rows.append(row)
    return rows


def run_isolated_grounding_case(case: dict[str, Any]) -> dict[str, Any]:
    """
    Run the grounding subsystem without an LLM call.

    The synthetic benchmark already contains a frozen structured job annotation. Using it
    isolates retrieval, deterministic evidence selection and deterministic composition from
    job-extraction quality and provider billing state.
    """
    expected = case.get("expected")
    if not isinstance(expected, dict):
        raise ValueError(f"{case.get('id', 'case')} has no structured expected annotation.")

    job_analysis = JobAnalysis(**expected)
    query = build_retrieval_query(job_analysis)
    documents = retrieve_profile_context(query, k=EMAIL_RETRIEVAL_K)
    retrieved_records = memory_documents_to_records(documents)
    if not retrieved_records:
        raise ValueError("No profile memories were retrieved for isolated grounding.")

    selection = deterministic_fallback_selection(
        retrieved_records,
        job_analysis=job_analysis,
    )
    email_draft = compose_grounded_email_draft(
        job_analysis=job_analysis,
        selection=selection,
        memory_records=retrieved_records,
    )
    return {
        "job_analysis": job_analysis.model_dump(),
        "retrieval_query": query,
        "retrieved_memories": [record["content"] for record in retrieved_records],
        "retrieved_memory_records": retrieved_records,
        "email_draft": email_draft.model_dump(),
    }


def run_end_to_end_case(case: dict[str, Any]) -> dict[str, Any]:
    """Run the complete product graph, including Anthropic-backed extraction and matching."""
    return jobcopilot_graph.invoke({"job_text": case["job_text"]})


def build_review_record(
    case: dict[str, Any],
    result: dict[str, Any],
    *,
    sampling: str,
    memory_profile: Path,
    execution_mode: ExecutionMode,
    memory_by_content: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    retrieved_records = list(result.get("retrieved_memory_records", []))
    if not retrieved_records:
        for content in result.get("retrieved_memories", []):
            record = memory_by_content.get(str(content).strip())
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
    return {
        "job_id": case["id"],
        "language": case.get("language", "unknown"),
        "category": case.get("category", "unknown"),
        "sampling_mode": sampling,
        "execution_mode": execution_mode,
        "memory_profile": str(memory_profile),
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
            "whether selected evidence is atomic and role-specific rather than merely generic."
        ),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_records(
    *,
    cases: list[dict[str, Any]],
    runner: Callable[[dict[str, Any]], dict[str, Any]],
    output: Path,
    errors_output: Path,
    manifest_output: Path,
    sampling: str,
    memory_profile: Path,
    execution_mode: ExecutionMode,
    memory_by_content: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate records incrementally so completed cases survive provider or case failures."""
    output.parent.mkdir(parents=True, exist_ok=True)
    errors_output.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    with output.open("w", encoding="utf-8") as review_handle, errors_output.open(
        "w", encoding="utf-8"
    ) as error_handle:
        for case_index, case in enumerate(cases):
            try:
                result = runner(case)
                record = build_review_record(
                    case,
                    result,
                    sampling=sampling,
                    memory_profile=memory_profile,
                    execution_mode=execution_mode,
                    memory_by_content=memory_by_content,
                )
                review_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                review_handle.flush()
                records.append(record)
            except Exception as exc:
                error = {
                    "job_id": case.get("id", "unknown"),
                    "case_index": case_index,
                    "category": case.get("category", "unknown"),
                    "execution_mode": execution_mode,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
                error_handle.write(json.dumps(error, ensure_ascii=False) + "\n")
                error_handle.flush()
                errors.append(error)
                break
            finally:
                write_json(
                    manifest_output,
                    {
                        "status": "partial" if errors else "running",
                        "execution_mode": execution_mode,
                        "requested_jobs": len(cases),
                        "completed_jobs": len(records),
                        "failed_jobs": len(errors),
                        "last_completed_job_id": records[-1]["job_id"] if records else None,
                        "failed_job_id": errors[-1]["job_id"] if errors else None,
                        "output": str(output),
                        "errors_output": str(errors_output),
                    },
                )

    write_json(
        manifest_output,
        {
            "status": "complete" if not errors and len(records) == len(cases) else "partial",
            "execution_mode": execution_mode,
            "requested_jobs": len(cases),
            "completed_jobs": len(records),
            "failed_jobs": len(errors),
            "last_completed_job_id": records[-1]["job_id"] if records else None,
            "failed_job_id": errors[-1]["job_id"] if errors else None,
            "output": str(output),
            "errors_output": str(errors_output),
        },
    )
    return records, errors


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
        default=Path("data/profile_memories.atomic.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/email_grounding_review.jsonl"),
    )
    parser.add_argument(
        "--errors-output",
        type=Path,
        default=Path("evaluation/results/email_grounding_errors.jsonl"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("evaluation/results/email_grounding_manifest.json"),
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
    parser.add_argument(
        "--execution-mode",
        choices=("isolated", "end-to-end"),
        default="isolated",
        help=(
            "isolated uses frozen benchmark job annotations and no Anthropic calls; "
            "end-to-end runs the complete product graph and requires Anthropic credits."
        ),
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Skip the first N selected cases for manual batch or resume workflows.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=0,
        help="Process at most N cases after start-index. Use zero for all remaining cases.",
    )
    args = parser.parse_args()

    if args.limit < 0 or args.start_index < 0 or args.max_cases < 0:
        raise ValueError("--limit, --start-index and --max-cases cannot be negative.")

    all_cases = load_jsonl(args.dataset)
    selected_cases = select_review_cases(
        all_cases,
        limit=args.limit,
        sampling=args.sampling,
    )
    cases = selected_cases[args.start_index :]
    if args.max_cases:
        cases = cases[: args.max_cases]
    if not cases:
        raise ValueError("No benchmark cases remain after applying the requested slice.")

    memories = load_profile_memories(args.memories)
    memory_by_content = {
        str(memory.get("content", "")).strip(): {
            key: value for key, value in memory.items() if value is not None
        }
        for memory in memories
        if str(memory.get("content", "")).strip()
    }

    runner = (
        run_isolated_grounding_case
        if args.execution_mode == "isolated"
        else run_end_to_end_case
    )
    records, errors = prepare_records(
        cases=cases,
        runner=runner,
        output=args.output,
        errors_output=args.errors_output,
        manifest_output=args.manifest_output,
        sampling=args.sampling,
        memory_profile=args.memories,
        execution_mode=args.execution_mode,
        memory_by_content=memory_by_content,
    )

    summary = {
        "status": "partial" if errors else "complete",
        "execution_mode": args.execution_mode,
        "requested_jobs": len(cases),
        "prepared_jobs": len(records),
        "failed_jobs": len(errors),
        "categories": sorted({record["category"] for record in records}),
        "sampling_mode": args.sampling,
        "memory_profile": str(args.memories),
        "composition_variants": sorted(
            {record["composition_variant"] for record in records}
        ),
        "unique_evidence_selections": len(
            {tuple(record["selected_memory_ids"]) for record in records}
        ),
        "proposed_claims": sum(
            len(record["proposed_claims"]) for record in records
        ),
        "output": str(args.output),
        "manifest_output": str(args.manifest_output),
        "errors_output": str(args.errors_output),
    }
    print(json.dumps(summary, indent=2))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
