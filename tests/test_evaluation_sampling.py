import pytest

from app.evaluation_sampling import select_review_cases


CASES = [
    {"id": "a1", "category": "A"},
    {"id": "a2", "category": "A"},
    {"id": "b1", "category": "B"},
    {"id": "b2", "category": "B"},
    {"id": "c1", "category": "C"},
]


def test_stratified_sampling_covers_categories_before_repeating():
    selected = select_review_cases(CASES, limit=3, sampling="stratified")

    assert [case["id"] for case in selected] == ["a1", "b1", "c1"]


def test_stratified_sampling_uses_deterministic_round_robin():
    selected = select_review_cases(CASES, limit=4, sampling="stratified")

    assert [case["id"] for case in selected] == ["a1", "b1", "c1", "a2"]


def test_head_sampling_preserves_dataset_order():
    selected = select_review_cases(CASES, limit=3, sampling="head")

    assert [case["id"] for case in selected] == ["a1", "a2", "b1"]


def test_zero_limit_returns_full_dataset():
    assert select_review_cases(CASES, limit=0) == CASES


def test_invalid_sampling_mode_is_rejected():
    with pytest.raises(ValueError, match="Unsupported sampling mode"):
        select_review_cases(CASES, limit=2, sampling="random")  # type: ignore[arg-type]
