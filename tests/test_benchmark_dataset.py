from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "evaluation" / "job_offers.v1.jsonl"
MANIFEST_PATH = PROJECT_ROOT / "evaluation" / "benchmark_manifest.v1.json"
RETRIEVAL_PATH = PROJECT_ROOT / "evaluation" / "retrieval_cases.v1.jsonl"
MEMORIES_PATH = PROJECT_ROOT / "data" / "profile_memories.example.json"


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_extraction_benchmark_matches_manifest():
    cases = load_jsonl(DATASET_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert len(cases) == 50
    assert len({case["id"] for case in cases}) == 50
    assert manifest["number_of_job_offers"] == len(cases)
    assert Counter(case["language"] for case in cases) == manifest["languages"]
    assert Counter(case["category"] for case in cases) == manifest["categories"]
    assert Counter(case["difficulty"] for case in cases) == manifest["difficulty"]


def test_extraction_cases_have_required_annotation_fields():
    required_expected_fields = {
        "company",
        "role",
        "location",
        "contract_type",
        "start_date",
        "required_skills",
        "preferred_skills",
        "tools_and_stack",
        "domain_focus",
    }

    for case in load_jsonl(DATASET_PATH):
        assert case["source_type"] == "synthetic"
        assert case["language"] in {"en", "fr"}
        assert case["difficulty"] in {"easy", "medium", "hard"}
        assert case["job_text"].strip()
        assert required_expected_fields <= set(case["expected"])


def test_retrieval_judgments_reference_existing_memories():
    memory_ids = {
        item["id"]
        for item in json.loads(MEMORIES_PATH.read_text(encoding="utf-8"))
    }
    cases = load_jsonl(RETRIEVAL_PATH)

    assert len(cases) == 20
    assert len({case["id"] for case in cases}) == 20

    for case in cases:
        assert case["query"].strip()
        assert case["relevant_ids"]
        assert set(case["relevant_ids"]) <= memory_ids
        assert set(case["relevance_by_id"]) <= memory_ids
