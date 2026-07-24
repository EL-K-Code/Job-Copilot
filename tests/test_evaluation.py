from app.evaluation import (
    evaluate_job_analysis,
    normalize_evaluation_item,
    set_precision_recall_f1,
)


def test_set_metrics_are_case_and_whitespace_insensitive():
    metrics = set_precision_recall_f1(
        predicted=[" Python ", "RAG"],
        expected=["python", "rag", "Docker"],
    )

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 2 / 3
    assert metrics["f1"] == 0.8


def test_acronyms_and_expanded_forms_are_equivalent():
    metrics = set_precision_recall_f1(
        predicted=[
            "Natural Language Processing (NLP)",
            "RAG (Retrieval-Augmented Generation)",
            "Large Language Model evaluation",
        ],
        expected=[
            "natural language processing",
            "RAG",
            "LLM evaluation",
        ],
    )

    assert metrics == {"precision": 1.0, "recall": 1.0, "f1": 1.0}


def test_alias_normalization_preserves_semantic_modifiers():
    assert normalize_evaluation_item("responsible AI") == "responsible ai"
    assert normalize_evaluation_item("agentic AI") == "agentic ai"

    metrics = set_precision_recall_f1(
        predicted=["responsible AI"],
        expected=["agentic AI"],
    )
    assert metrics["f1"] == 0.0


def test_job_analysis_evaluation_combines_scalar_and_list_scores():
    result = evaluate_job_analysis(
        predicted={
            "company": "Example Labs",
            "role": "ML Engineer",
            "required_skills": ["Python", "SQL"],
            "tools_and_stack": ["Docker"],
        },
        expected={
            "company": "example labs",
            "role": "ML Engineer",
            "required_skills": ["Python", "SQL"],
            "tools_and_stack": ["Docker", "Kubernetes"],
        },
    )

    assert result["scalar_accuracy"] == 1.0
    assert result["list_fields"]["required_skills"]["f1"] == 1.0
    assert result["list_fields"]["tools_and_stack"]["recall"] == 0.5


def test_generated_highlights_are_excluded_from_extraction_f1():
    result = evaluate_job_analysis(
        predicted={
            "required_skills": ["Python"],
            "key_highlights_for_candidate": [
                "Showcase production-grade Python projects"
            ],
        },
        expected={
            "required_skills": ["Python"],
            "key_highlights_for_candidate": ["Python"],
        },
    )

    assert result["macro_list_f1"] == 1.0
    assert "key_highlights_for_candidate" not in result["list_fields"]
    assert "key_highlights_for_candidate" in result["unscored_fields"]
