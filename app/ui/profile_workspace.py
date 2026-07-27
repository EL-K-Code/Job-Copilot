from __future__ import annotations

import json
from collections import Counter
from html import escape
from typing import Any

import streamlit as st

from app.services.llm_telemetry import (
    capture_llm_telemetry,
    serialize_llm_events,
    summarize_llm_events,
)
from app.services.profile_onboarding import (
    PROFILE_TYPES,
    build_profile_memories,
    extraction_to_review_rows,
    extract_profile_facts,
    manual_profile_to_review_rows,
    memories_to_review_rows,
    prepare_cv_documents,
)
from app.services.profile_store import (
    load_user_profile_memories,
    save_user_profile_memories,
)
from app.tenancy import ensure_user_directories


_CATEGORY_LABELS = {
    "identity": "Professional summary",
    "experience": "Experience",
    "project": "Project",
    "education": "Education",
    "skill": "Skill",
    "language": "Language",
    "certification": "Certification",
    "achievement": "Achievement",
    "preference": "Career preference",
}


def _state_key(user_id: str, suffix: str) -> str:
    return f"profile_workspace:{user_id}:{suffix}"


def _load_existing(user_id: str) -> list[dict[str, Any]]:
    paths = ensure_user_directories(user_id)
    if not paths.profile_memories.exists():
        return []
    return load_user_profile_memories(user_id)


def _set_draft(
    user_id: str,
    rows: list[dict[str, Any]],
    *,
    source_label: str,
    replace_existing: bool = False,
    telemetry: list[dict[str, Any]] | None = None,
) -> None:
    st.session_state[_state_key(user_id, "rows")] = rows
    st.session_state[_state_key(user_id, "source")] = source_label
    st.session_state[_state_key(user_id, "replace")] = replace_existing
    st.session_state[_state_key(user_id, "telemetry")] = telemetry or []
    st.session_state.pop(_state_key(user_id, "editor"), None)


def _clear_draft(user_id: str) -> None:
    for suffix in ("rows", "source", "replace", "telemetry", "editor"):
        st.session_state.pop(_state_key(user_id, suffix), None)


def _render_trace(events: list[dict[str, Any]]) -> None:
    if not events:
        return
    summary = summarize_llm_events(events)
    provider = str(summary.get("final_provider") or "unknown").title()
    model = str(summary.get("final_model") or "unknown")
    duration = float(summary.get("total_duration_ms", 0) or 0) / 1000
    fallback = " · fallback used" if summary.get("fallback_used") else ""
    st.markdown(
        f"""
        <div class="jc-provider">
          <strong>CV extraction trace:</strong> {escape(provider)} · {escape(model)} · {duration:.2f}s{fallback}<br>
          <span class="jc-muted">Only provider metadata is retained. Raw CV text, prompts, model output and API keys are not logged.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Technical extraction trace"):
        st.dataframe(events, use_container_width=True, hide_index=True)


def _render_cv_import(user_id: str) -> None:
    st.markdown("#### Import one or more CVs")
    st.caption(
        "PDF, DOCX or TXT · up to 5 files · 10 MB per file. Older role-specific CV versions can be combined."
    )
    uploads = st.file_uploader(
        "Choose my CV files",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key=_state_key(user_id, "cv_uploads"),
    )
    st.info(
        "Text is extracted locally first. When you click Analyze, the extracted text is sent to the configured AI provider to propose facts. The original files are not stored by JobCopilot."
    )
    consent = st.checkbox(
        "I understand and want JobCopilot to analyze the selected CV text.",
        key=_state_key(user_id, "cv_consent"),
    )
    if st.button(
        "Analyze my CVs",
        type="primary",
        use_container_width=True,
        disabled=not uploads or not consent,
        key=_state_key(user_id, "analyze_cvs"),
    ):
        try:
            documents = prepare_cv_documents(
                [(upload.name, upload.getvalue()) for upload in uploads]
            )
            with st.spinner("Extracting conservative profile facts for your review..."):
                with capture_llm_telemetry() as events:
                    extraction = extract_profile_facts(documents)
            rows = extraction_to_review_rows(extraction)
            if not rows:
                raise ValueError(
                    "No reliable profile facts were extracted. Try a text-based CV or use the manual profile form."
                )
            _set_draft(
                user_id,
                rows,
                source_label=f"{len(documents)} CV file(s)",
                telemetry=serialize_llm_events(events),
            )
            st.success(
                f"{len(rows)} proposed facts found. Review every row below before activation."
            )
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _render_manual_profile(user_id: str) -> None:
    st.markdown("#### Fill in my profile")
    st.caption(
        "Write one factual statement per line. You will review and edit everything before it becomes application evidence."
    )
    with st.form(_state_key(user_id, "manual_form")):
        identity = st.text_area(
            "Professional summary",
            placeholder="I am an early-career machine learning engineer focused on reliable applied AI.",
            height=90,
        )
        experience = st.text_area(
            "Experience facts",
            placeholder="Built a data validation pipeline in Python.\nEvaluated a model using ROC-AUC and threshold analysis.",
            height=125,
        )
        projects = st.text_area(
            "Project facts",
            placeholder="Developed an agentic workflow with LangGraph.\nCreated a FastAPI inference endpoint.",
            height=125,
        )
        education = st.text_area(
            "Education",
            placeholder="Completed a Master's degree in Data Science at ...",
            height=90,
        )
        skills = st.text_area(
            "Technical skills",
            placeholder="Use Python for data science and machine learning.\nUse SQL for data analysis.",
            height=110,
        )
        languages = st.text_area(
            "Languages",
            placeholder="Speak French fluently.\nUse English at an intermediate professional level.",
            height=90,
        )
        certifications = st.text_area(
            "Certifications",
            placeholder="Completed the ... certification in 2025.",
            height=80,
        )
        achievements = st.text_area(
            "Achievements",
            placeholder="Presented ... at ...",
            height=80,
        )
        preferences = st.text_area(
            "Career preferences",
            placeholder="Interested in junior AI/ML roles and applied research opportunities.",
            height=80,
        )
        submitted = st.form_submit_button(
            "Create my review draft",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        try:
            rows = manual_profile_to_review_rows(
                {
                    "identity": identity,
                    "experience": experience,
                    "project": projects,
                    "education": education,
                    "skill": skills,
                    "language": languages,
                    "certification": certifications,
                    "achievement": achievements,
                    "preference": preferences,
                }
            )
            if not rows:
                raise ValueError("Add at least one profile fact before continuing.")
            _set_draft(user_id, rows, source_label="Manual profile")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _render_advanced_restore(user_id: str) -> None:
    st.markdown("#### Restore a JobCopilot backup")
    st.caption(
        "Advanced option for an exported profile_memories.json file. Normal users do not need this."
    )
    upload = st.file_uploader(
        "JobCopilot profile backup",
        type=["json"],
        key=_state_key(user_id, "json_restore"),
    )
    replace = st.checkbox(
        "Replace my current profile after review",
        value=True,
        key=_state_key(user_id, "json_replace"),
    )
    if st.button(
        "Review this backup",
        use_container_width=True,
        disabled=upload is None,
        key=_state_key(user_id, "review_json"),
    ):
        try:
            payload = json.loads(upload.getvalue().decode("utf-8"))
            if not isinstance(payload, list):
                raise ValueError("The backup must contain a list of profile facts.")
            required = {"id", "type", "content"}
            for item in payload:
                if not isinstance(item, dict) or not required.issubset(item):
                    raise ValueError(
                        "Every backup fact must include id, type and content."
                    )
            _set_draft(
                user_id,
                memories_to_review_rows(payload),
                source_label="JobCopilot backup",
                replace_existing=replace,
            )
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _render_review(user_id: str, existing: list[dict[str, Any]]) -> None:
    rows = st.session_state.get(_state_key(user_id, "rows"))
    if not rows:
        return

    st.divider()
    st.markdown("### Review and approve your profile facts")
    st.caption(
        "Nothing is activated automatically. Uncheck, edit, delete or add rows until every selected statement is accurate."
    )
    counts = Counter(str(row.get("Category", "other")) for row in rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("Proposed facts", len(rows))
    c2.metric("Categories", len(counts))
    c3.metric("Source", st.session_state.get(_state_key(user_id, "source"), "Draft"))

    edited_rows = st.data_editor(
        rows,
        key=_state_key(user_id, "editor"),
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_order=("Use", "Category", "Fact", "Source"),
        column_config={
            "Use": st.column_config.CheckboxColumn(
                "Keep",
                help="Only checked facts become evidence.",
                default=True,
                width="small",
            ),
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=list(PROFILE_TYPES),
                required=True,
                width="medium",
            ),
            "Fact": st.column_config.TextColumn(
                "Verified fact",
                required=True,
                width="large",
            ),
            "Source": st.column_config.TextColumn(
                "Source",
                width="medium",
            ),
        },
    )

    telemetry = st.session_state.get(_state_key(user_id, "telemetry"), [])
    _render_trace(telemetry)

    replace_default = bool(
        st.session_state.get(_state_key(user_id, "replace"), False)
    )
    replace = False
    if existing:
        replace = st.toggle(
            "Replace my current profile instead of adding these verified facts",
            value=replace_default,
            key=_state_key(user_id, "replace_toggle"),
        )
        if not replace:
            st.caption(
                f"These facts will be merged with your {len(existing)} existing verified facts; duplicates are removed."
            )

    left, right = st.columns([1, 1])
    with left:
        if st.button(
            "Activate verified profile",
            type="primary",
            use_container_width=True,
            key=_state_key(user_id, "activate"),
        ):
            try:
                memories = build_profile_memories(
                    edited_rows,
                    existing_memories=[] if replace else existing,
                )
                save_user_profile_memories(user_id, memories)
                _clear_draft(user_id)
                st.success(
                    f"Profile activated with {len(memories)} verified facts."
                )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with right:
        if st.button(
            "Discard this draft",
            use_container_width=True,
            key=_state_key(user_id, "discard"),
        ):
            _clear_draft(user_id)
            st.rerun()


def _render_builder(user_id: str, *, existing: list[dict[str, Any]]) -> None:
    import_tab, manual_tab, advanced_tab = st.tabs(
        ["Import CVs", "Fill manually", "Advanced restore"]
    )
    with import_tab:
        _render_cv_import(user_id)
    with manual_tab:
        _render_manual_profile(user_id)
    with advanced_tab:
        _render_advanced_restore(user_id)
    _render_review(user_id, existing)


def render_profile_gate(user_id: str) -> bool:
    """Render first-use onboarding and return True only after a profile exists."""
    existing = _load_existing(user_id)
    if existing:
        return True

    st.markdown(
        """
        <div class="jc-hero">
          <div class="jc-eyebrow">Profile setup · human verified</div>
          <h1>Build your JobCopilot profile</h1>
          <p>Import existing CVs or fill in your profile. JobCopilot proposes structured facts, but you decide exactly what may be used in an application.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.7, 1])
    with left:
        _render_builder(user_id, existing=[])
    with right:
        st.markdown(
            """
            <div class="jc-card">
              <div class="jc-card-title">Your approval is the safety layer</div>
              <p class="jc-muted">CV extraction creates only a draft. Every fact must remain checked in the review table before activation.</p>
              <span class="jc-pill jc-pill-success">Human verified</span>
              <span class="jc-pill">Evidence grounded</span>
              <span class="jc-pill">User isolated</span>
              <span class="jc-pill">Exportable</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    return False


def render_profile_page(user_id: str) -> None:
    existing = _load_existing(user_id)
    st.markdown(
        """
        <div class="jc-hero">
          <div class="jc-eyebrow">Verified evidence profile</div>
          <h1>Manage your profile</h1>
          <p>Add facts from another CV, complete your profile manually, or review the evidence JobCopilot is allowed to use.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if existing:
        counts = Counter(str(memory.get("type", "other")) for memory in existing)
        c1, c2, c3 = st.columns(3)
        c1.metric("Verified facts", len(existing))
        c2.metric("Categories", len(counts))
        c3.metric("Grounding status", "Active")
        with st.expander("Review my current verified facts"):
            st.dataframe(
                [
                    {
                        "Category": _CATEGORY_LABELS.get(
                            str(memory.get("type", "")),
                            str(memory.get("type", "")).title(),
                        ),
                        "Fact": memory.get("content", ""),
                        "Source": memory.get("source", "Existing profile"),
                    }
                    for memory in existing
                ],
                use_container_width=True,
                hide_index=True,
            )
            if st.button(
                "Edit or remove existing facts",
                use_container_width=True,
                key=_state_key(user_id, "edit_existing"),
            ):
                _set_draft(
                    user_id,
                    memories_to_review_rows(existing),
                    source_label="Current profile",
                    replace_existing=True,
                )
                st.rerun()
    else:
        st.warning("No active profile found. Complete the setup below.")

    st.markdown("### Add or update profile information")
    _render_builder(user_id, existing=existing)
