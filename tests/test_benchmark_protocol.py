import json
from pathlib import Path

from app.prompts import JOB_ANALYSIS_SYSTEM_PROMPT


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SMOKE_DATASET = PROJECT_ROOT / "evaluation" / "job_offers.smoke.v1.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_smoke_suite_is_stratified():
    cases = load_jsonl(SMOKE_DATASET)

    assert len(cases) == 5
    assert {case["language"] for case in cases} == {"en", "fr"}
    assert len({case["category"] for case in cases}) == 5
    assert {case["difficulty"] for case in cases} == {"easy", "medium", "hard"}


def test_smoke_suite_contains_missing_contract_challenge():
    challenge = next(case for case in load_jsonl(SMOKE_DATASET) if case["id"] == "smoke_001")

    assert "Intern" in challenge["expected"]["role"]
    assert challenge["expected"]["contract_type"] == "Unknown"


def test_job_analysis_prompt_forbids_contract_inference_from_title():
    assert "Never infer contract_type from the role title" in JOB_ANALYSIS_SYSTEM_PROMPT
    assert "Otherwise return \"Unknown\"" in JOB_ANALYSIS_SYSTEM_PROMPT
