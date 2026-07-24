from app.evaluation import evaluate_job_analysis, set_precision_recall_f1


def test_set_metrics_are_case_and_whitespace_insensitive():
    metrics = set_precision_recall_f1(
        predicted=[" Python ", "RAG"],
        expected=["python", "rag", "Docker"],
    )

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 2 / 3
    assert metrics["f1"] == 0.8


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
