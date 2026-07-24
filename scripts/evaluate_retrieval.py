from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation import evaluate_retrieval_ranking
from app.memory import build_profile_vector_store, load_profile_memories


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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_evaluation(
    cases: list[dict],
    memories_path: Path,
    top_k: int = 5,
) -> dict:
    memories = load_profile_memories(memories_path)
    vector_store = build_profile_vector_store(memories)
    case_results: list[dict] = []

    for case in cases:
        results = vector_store.similarity_search_with_score(case["query"], k=top_k)
        retrieved = [
            {
                "id": str(document.metadata.get("id", "")),
                "content": document.page_content,
                "distance": float(score),
            }
            for document, score in results
        ]
        retrieved_ids = [item["id"] for item in retrieved]
        metrics = evaluate_retrieval_ranking(
            retrieved_ids=retrieved_ids,
            relevant_ids=case["relevant_ids"],
            relevance_by_id=case.get("relevance_by_id"),
            ks=(1, 3, 5),
        )
        case_results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "relevant_ids": case["relevant_ids"],
                "retrieved": retrieved,
                "metrics": metrics,
            }
        )

    metric_names = (
        "reciprocal_rank",
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "ndcg_at_1",
        "ndcg_at_3",
        "ndcg_at_5",
    )
    aggregate = {
        metric_name: mean(
            item["metrics"][metric_name] for item in case_results
        ) if case_results else 0.0
        for metric_name in metric_names
    }

    return {
        "task": "profile_memory_retrieval",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "number_of_cases": len(case_results),
        "top_k": top_k,
        "aggregate": aggregate,
        "cases": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate profile-memory retrieval on relevance judgments."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/retrieval_cases.v1.jsonl"),
    )
    parser.add_argument(
        "--memories",
        type=Path,
        default=Path("data/profile_memories.example.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/retrieval_report.json"),
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    if args.top_k < 5:
        raise ValueError("--top-k must be at least 5 for the benchmark metrics.")

    report = run_evaluation(
        load_jsonl(args.dataset),
        memories_path=args.memories,
        top_k=args.top_k,
    )
    report["dataset_sha256"] = sha256_file(args.dataset)
    report["memories_sha256"] = sha256_file(args.memories)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({**report["aggregate"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
