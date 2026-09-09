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
from app.retrieval import retrieve_profile_context_with_scores


STRATEGY_CONFIGS = {
    "dense": {"strategy": "dense", "rerank": False},
    "hybrid": {"strategy": "hybrid", "rerank": False},
    "hybrid_rerank": {"strategy": "hybrid", "rerank": True},
}
METRIC_NAMES = [
    "mrr",
    "recall@1",
    "recall@3",
    "recall@5",
    "ndcg@1",
    "ndcg@3",
    "ndcg@5",
]


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def evaluate_strategy(cases: list[dict], strategy_name: str, *, k: int) -> dict:
    config = STRATEGY_CONFIGS[strategy_name]
    results = []
    for case in cases:
        retrieved = retrieve_profile_context_with_scores(
            case["query"],
            k=k,
            strategy=str(config["strategy"]),
            rerank=bool(config["rerank"]),
        )
        ranked_ids = [
            str(document.metadata.get("id", ""))
            for document, _score in retrieved
        ]
        metrics = evaluate_retrieval_ranking(
            ranked_ids,
            case["relevant_memory_ids"],
        )
        results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "ranked_memory_ids": ranked_ids,
                "relevant_memory_ids": case["relevant_memory_ids"],
                "metrics": metrics,
            }
        )

    return {
        "aggregate": {
            name: mean(item["metrics"][name] for item in results)
            if results
            else 0.0
            for name in METRIC_NAMES
        },
        "cases": results,
    }


def run(
    cases: list[dict],
    k: int = 5,
    strategies: list[str] | None = None,
) -> dict:
    selected = strategies or list(STRATEGY_CONFIGS)
    invalid = [name for name in selected if name not in STRATEGY_CONFIGS]
    if invalid:
        raise ValueError(f"Unsupported retrieval strategies: {', '.join(invalid)}")

    strategy_reports = {
        name: evaluate_strategy(cases, name, k=k)
        for name in selected
    }
    default_strategy = (
        "hybrid_rerank"
        if "hybrid_rerank" in strategy_reports
        else selected[0]
    )
    default_report = strategy_reports[default_strategy]

    return {
        "number_of_cases": len(cases),
        "k": k,
        "default_strategy": default_strategy,
        # Backward-compatible aliases for existing consumers.
        "aggregate": default_report["aggregate"],
        "cases": default_report["cases"],
        "strategies": strategy_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate and compare profile-memory retrieval strategies."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/retrieval_cases.v1.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results/retrieval_report.json"),
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=sorted(STRATEGY_CONFIGS),
        default=list(STRATEGY_CONFIGS),
        help="Retrieval strategies to compare on the same benchmark cases.",
    )
    args = parser.parse_args()

    report = run(
        load_jsonl(args.dataset),
        k=args.k,
        strategies=args.strategies,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary = {
        name: strategy_report["aggregate"]
        for name, strategy_report in report["strategies"].items()
    }
    print(
        json.dumps(
            {
                "number_of_cases": report["number_of_cases"],
                "strategies": summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
