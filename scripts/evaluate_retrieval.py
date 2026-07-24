from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation import evaluate_retrieval_ranking
from app.memory import retrieve_profile_context_with_scores


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(cases: list[dict], k: int = 5) -> dict:
    results = []
    for case in cases:
        retrieved = retrieve_profile_context_with_scores(case["query"], k=k)
        ranked_ids = [str(document.metadata.get("id", "")) for document, _ in retrieved]
        metrics = evaluate_retrieval_ranking(ranked_ids, case["relevant_memory_ids"])
        results.append({
            "id": case["id"],
            "query": case["query"],
            "ranked_memory_ids": ranked_ids,
            "relevant_memory_ids": case["relevant_memory_ids"],
            "metrics": metrics,
        })
    metric_names = ["mrr", "recall@1", "recall@3", "recall@5", "ndcg@1", "ndcg@3", "ndcg@5"]
    return {
        "number_of_cases": len(results),
        "aggregate": {
            name: mean(item["metrics"][name] for item in results) if results else 0.0
            for name in metric_names
        },
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate profile-memory retrieval.")
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/retrieval_cases.v1.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/retrieval_report.json"))
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    report = run(load_jsonl(args.dataset), k=args.k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"number_of_cases": report["number_of_cases"], **report["aggregate"]}, indent=2))


if __name__ == "__main__":
    main()
