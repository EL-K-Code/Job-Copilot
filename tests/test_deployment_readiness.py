from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.email_composer import compose_grounded_email_draft
from app.schemas import EmailEvidenceSelection, JobAnalysis
from app.services import usage_quota
from app.services.usage_quota import UsageQuotaExceeded
from app.ui.private_beta_shell import _effective_user


def _configure_quota_root(monkeypatch, tmp_path, *, limit: int = 2) -> None:
    monkeypatch.setattr(
        "app.tenancy.settings",
        SimpleNamespace(user_data_root_path=tmp_path / "users"),
    )
    monkeypatch.setattr(
        usage_quota,
        "settings",
        SimpleNamespace(beta_daily_ai_limit=limit),
    )


def test_daily_quota_is_tenant_scoped_and_blocks_after_limit(monkeypatch, tmp_path):
    _configure_quota_root(monkeypatch, tmp_path, limit=2)
    today = date(2026, 7, 27)

    first = usage_quota.consume_ai_operation("alice", "application analysis", day=today)
    second = usage_quota.consume_ai_operation("alice", "cv extraction", day=today)
    bob = usage_quota.consume_ai_operation("bob", "agent chat", day=today)

    assert first.used == 1
    assert first.remaining == 1
    assert second.used == 2
    assert second.remaining == 0
    assert second.operations == {
        "application_analysis": 1,
        "cv_extraction": 1,
    }
    assert bob.used == 1
    assert bob.remaining == 1

    with pytest.raises(UsageQuotaExceeded, match="Daily AI quota reached"):
        usage_quota.consume_ai_operation("alice", "agent chat", day=today)


def test_daily_quota_resets_on_a_new_day(monkeypatch, tmp_path):
    _configure_quota_root(monkeypatch, tmp_path, limit=1)

    usage_quota.consume_ai_operation(
        "alice",
        "application_analysis",
        day=date(2026, 7, 27),
    )
    next_day = usage_quota.consume_ai_operation(
        "alice",
        "application_analysis",
        day=date(2026, 7, 28),
    )

    assert next_day.used == 1
    assert next_day.remaining == 0
    assert next_day.day == "2026-07-28"


def test_email_signature_uses_trusted_candidate_name_without_placeholder():
    analysis = JobAnalysis(
        company="Example AI",
        role="Machine Learning Engineer",
        required_skills=["Python"],
        tools_and_stack=["Python"],
        domain_focus=["Machine Learning"],
    )
    memories = [
        {
            "id": "skill_python",
            "type": "skill",
            "topic": "python",
            "group_id": "skills",
            "content": "The candidate uses Python for machine learning.",
        }
    ]
    draft = compose_grounded_email_draft(
        analysis,
        EmailEvidenceSelection(selected_memory_ids=["skill_python"]),
        memories,
        candidate_name="  Komla Alex\nLABOU  ",
    )

    assert draft.body.endswith("Kind regards,\nKomla Alex LABOU")
    assert "[Candidate Name]" not in draft.body


def test_email_signature_omits_unknown_name_instead_of_showing_placeholder():
    analysis = JobAnalysis(
        company="Example AI",
        role="Machine Learning Engineer",
        required_skills=["Python"],
        tools_and_stack=["Python"],
    )
    memories = [
        {
            "id": "skill_python",
            "type": "skill",
            "topic": "python",
            "content": "The candidate uses Python for machine learning.",
        }
    ]
    draft = compose_grounded_email_draft(
        analysis,
        EmailEvidenceSelection(selected_memory_ids=["skill_python"]),
        memories,
    )

    assert draft.body.endswith("Kind regards,")
    assert "Candidate Name" not in draft.body


def test_local_candidate_name_overrides_demo_label(monkeypatch):
    monkeypatch.setattr(
        "app.ui.private_beta_shell.settings",
        SimpleNamespace(local_candidate_name="Komla Alex LABOU"),
    )

    user = _effective_user(
        {"user_id": "local-demo", "display_name": "Local demo"}
    )

    assert user == {
        "user_id": "local-demo",
        "display_name": "Komla Alex LABOU",
    }
