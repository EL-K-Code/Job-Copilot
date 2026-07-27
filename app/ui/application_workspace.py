from __future__ import annotations

import hashlib
from datetime import date, timedelta
from html import escape
from uuid import uuid4

import streamlit as st

from app.services.applications_store import (
    add_application_record,
    create_application_record,
    find_existing_application,
)
from app.services.llm_telemetry import (
    capture_llm_telemetry,
    serialize_llm_events,
    summarize_llm_events,
)
from app.services.usage_quota import UsageQuotaExceeded
from app.tools.calendar_tools import build_followup_event_payload, create_followup_event
from app.tools.gmail_tools import create_gmail_draft, google_token_exists


JOB_PLACEHOLDER = "Paste the complete job description here."


def normalize_initial_job_text(value: str | None) -> str:
    """Remove the legacy placeholder when it was stored as real widget content."""
    normalized = str(value or "")
    return "" if normalized.strip() == JOB_PLACEHOLDER else normalized


def evidence_records_for_claim(
    claim: dict,
    memory_records: list[dict],
) -> list[dict]:
    """Return only the retrieved memories explicitly cited by one claim."""
    by_id = {
        str(record.get("id", "")).strip(): record
        for record in memory_records
        if str(record.get("id", "")).strip()
    }
    return [
        by_id[memory_id]
        for memory_id in claim.get("supporting_memory_ids", [])
        if memory_id in by_id
    ]


def telemetry_badges(events: list[dict], claim_count: int) -> dict[str, str | bool]:
    """Build a compact, user-facing transparency summary."""
    summary = summarize_llm_events(events)
    provider = str(summary.get("final_provider") or "AI").title()
    model = str(summary.get("final_model") or "unknown")
    return {
        "provider": provider,
        "model": model,
        "fallback_used": bool(summary.get("fallback_used")),
        "grounding_label": f"{claim_count} grounded claim{'s' if claim_count != 1 else ''}",
    }


def _run_pipeline(
    user_id: str,
    candidate_name: str,
    job_text: str,
) -> dict:
    from app.graph import jobcopilot_graph

    with capture_llm_telemetry() as events:
        result = jobcopilot_graph.invoke(
            {
                "user_id": user_id,
                "candidate_name": candidate_name,
                "job_text": job_text,
            },
            config={
                "configurable": {
                    "thread_id": f"private-beta-{user_id}-{uuid4()}"
                }
            },
        )
    serialized = serialize_llm_events(events)
    return {
        "job_analysis": result["job_analysis"],
        "retrieved_memories": result["retrieved_memories"],
        "retrieved_memory_records": result.get("retrieved_memory_records", []),
        "match": result["match_insight"],
        "email_draft": result["email_draft"],
        "llm_telemetry": serialized,
        "llm_telemetry_summary": summarize_llm_events(serialized),
    }


def _render_compact_ai_status(events: list[dict], claim_count: int) -> None:
    badges = telemetry_badges(events, claim_count)
    fallback = (
        '<span class="jc-pill">Fallback used</span>'
        if badges["fallback_used"]
        else ""
    )
    st.markdown(
        (
            '<div class="jc-trust-row">'
            f'<span class="jc-pill jc-pill-success">Generated with {escape(str(badges["provider"]))}</span>'
            f'<span class="jc-pill">{escape(str(badges["grounding_label"]))}</span>'
            f'{fallback}'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def _render_technical_trace(events: list[dict]) -> None:
    if not events:
        return
    summary = summarize_llm_events(events)
    provider = str(summary.get("final_provider") or "unknown").title()
    model = str(summary.get("final_model") or "unknown")
    duration = float(summary.get("total_duration_ms", 0) or 0) / 1000
    successful = int(summary.get("successful_calls", 0) or 0)
    failed = int(summary.get("failed_attempts", 0) or 0)
    with st.expander("AI transparency & technical details"):
        st.write(f"**Provider used:** {provider}")
        st.write(f"**Model:** {model}")
        st.write(
            f"**Execution:** {successful} successful call(s), "
            f"{failed} failed attempt(s), {duration:.2f}s"
        )
        st.caption(
            "This trace stores provider metadata only. Job text, prompts, generated content and API keys are not recorded here."
        )
        st.dataframe(events, use_container_width=True, hide_index=True)


def _sync_email_editor(draft: dict, analysis: dict) -> None:
    signature_source = "|".join(
        [
            str(analysis.get("company", "")),
            str(analysis.get("role", "")),
            str(draft.get("subject", "")),
            str(draft.get("body", "")),
        ]
    )
    signature = hashlib.sha256(signature_source.encode("utf-8")).hexdigest()
    if st.session_state.get("application_result_signature") == signature:
        return
    st.session_state["application_result_signature"] = signature
    st.session_state["beta_email_subject"] = str(draft.get("subject", ""))
    st.session_state["beta_email_body"] = str(draft.get("body", ""))
    st.session_state["beta_recipient"] = ""
    st.session_state["beta_message_reviewed"] = False


def _render_role_overview(analysis: dict) -> None:
    left, right = st.columns(2)
    with left:
        st.markdown("#### Main responsibilities")
        missions = analysis.get("missions_summary", [])
        if missions:
            for item in missions:
                st.write(f"• {item}")
        else:
            st.caption("No explicit responsibilities were extracted.")
        st.markdown("#### Required skills")
        pills = " ".join(
            f'<span class="jc-pill">{escape(str(item))}</span>'
            for item in analysis.get("required_skills", [])
        )
        st.markdown(pills or "—", unsafe_allow_html=True)
    with right:
        st.markdown("#### Tools and stack")
        pills = " ".join(
            f'<span class="jc-pill">{escape(str(item))}</span>'
            for item in analysis.get("tools_and_stack", [])
        )
        st.markdown(pills or "—", unsafe_allow_html=True)
        st.markdown("#### Domain focus")
        pills = " ".join(
            f'<span class="jc-pill">{escape(str(item))}</span>'
            for item in analysis.get("domain_focus", [])
        )
        st.markdown(pills or "—", unsafe_allow_html=True)


def _render_match_and_evidence(match: dict, draft: dict, memory_records: list[dict]) -> None:
    strengths, gaps = st.columns(2)
    with strengths:
        st.markdown("#### Strong alignment")
        items = match.get("strengths", [])
        if items:
            for item in items:
                st.success(item)
        else:
            st.caption("No strong alignment was asserted.")
    with gaps:
        st.markdown("#### Points to handle honestly")
        items = match.get("gaps", [])
        if items:
            for item in items:
                st.warning(item)
        else:
            st.caption("No material gap was identified from the supplied offer.")

    claims = draft.get("claim_evidence", [])
    st.markdown(f"#### Evidence used in the email · {len(claims)}")
    if not claims:
        st.info("The email contains no factual candidate claim requiring evidence.")
        return

    for index, claim in enumerate(claims, start=1):
        supporting = evidence_records_for_claim(claim, memory_records)
        with st.container(border=True):
            st.markdown(f"**{index}. {claim.get('claim', '')}**")
            for record in supporting:
                st.markdown(
                    f'<div class="jc-evidence-fact">Verified profile fact · {escape(str(record.get("content", "")))}</div>',
                    unsafe_allow_html=True,
                )
            aligned = claim.get("aligned_job_terms", [])
            if aligned:
                st.caption("Aligned with: " + ", ".join(str(item) for item in aligned))
            with st.expander("Audit metadata"):
                st.write("Memory IDs: " + ", ".join(claim.get("supporting_memory_ids", [])))
                st.write(
                    f"Relevance score: {float(claim.get('relevance_score', 0) or 0):.2f}"
                )


def _render_email_actions(user_id: str, analysis: dict, draft: dict) -> None:
    _sync_email_editor(draft, analysis)
    st.markdown(
        '<div class="jc-step">Step 2 · Review the message</div>',
        unsafe_allow_html=True,
    )
    subject = st.text_input("Subject", key="beta_email_subject")
    body = st.text_area("Email body", height=360, key="beta_email_body")

    st.markdown(
        '<div class="jc-step">Step 3 · Choose the next action</div>',
        unsafe_allow_html=True,
    )
    connected = google_token_exists(user_id)
    recipient = st.text_input(
        "Recruiter email",
        key="beta_recipient",
        placeholder="recruiter@company.com",
    )
    followup_date = st.date_input(
        "Follow-up date",
        value=date.today() + timedelta(days=5),
        min_value=date.today(),
        key="beta_followup_date",
    )
    reviewed = st.checkbox(
        "I reviewed the recipient, subject and email body.",
        key="beta_message_reviewed",
    )

    if not connected:
        st.info(
            "Connect Google in Settings to create Gmail drafts and Calendar reminders. "
            "Saving to the tracker remains available."
        )

    save_col, gmail_col, calendar_col = st.columns(3)
    with save_col:
        if st.button("Save to tracker", use_container_width=True, key="premium_save_tracker"):
            existing = find_existing_application(
                str(analysis.get("company", "")),
                str(analysis.get("role", "")),
                user_id=user_id,
            )
            if existing:
                st.warning("This application already exists in your tracker.")
            else:
                record = create_application_record(
                    company=str(analysis.get("company", "")),
                    role=str(analysis.get("role", "")),
                    email_subject=subject,
                    email_body=body,
                    source="private-beta",
                    reminder_date=str(followup_date),
                )
                add_application_record(record, user_id=user_id)
                st.success("Saved to your private tracker.")

    can_use_google = connected and reviewed and bool(recipient.strip())
    with gmail_col:
        if st.button(
            "Create Gmail draft",
            type="primary",
            use_container_width=True,
            disabled=not can_use_google,
            key="premium_create_gmail_draft",
        ):
            try:
                create_gmail_draft(
                    to=recipient,
                    subject=subject,
                    body=body,
                    user_id=user_id,
                )
                st.success("Gmail draft created. Review it in Gmail before sending.")
            except Exception as exc:
                st.error(f"The Gmail draft could not be created ({type(exc).__name__}).")

    with calendar_col:
        if st.button(
            "Add follow-up",
            use_container_width=True,
            disabled=not connected,
            key="premium_add_followup",
        ):
            try:
                payload = build_followup_event_payload(
                    company=str(analysis.get("company", "")),
                    role=str(analysis.get("role", "")),
                    followup_date=str(followup_date),
                )
                create_followup_event(**payload, user_id=user_id)
                st.success("Follow-up reminder added to Google Calendar.")
            except Exception as exc:
                st.error(f"The Calendar reminder could not be created ({type(exc).__name__}).")


def render_application_workspace(user: dict[str, str]) -> None:
    """Render the polished offer-to-application workflow."""
    user_id = user["user_id"]
    candidate_name = str(user.get("display_name", "")).strip()

    st.markdown("## New application")
    st.caption(
        "Turn a complete job description into a reviewed, evidence-grounded application draft."
    )

    current = normalize_initial_job_text(st.session_state.get("job_text"))
    if st.session_state.get("job_text") != current:
        st.session_state["job_text"] = current

    with st.container(border=True):
        st.markdown(
            '<div class="jc-step">Step 1 · Opportunity</div>',
            unsafe_allow_html=True,
        )
        job_text = st.text_area(
            "Job description",
            height=280,
            key="job_text",
            placeholder=JOB_PLACEHOLDER,
            label_visibility="collapsed",
        )
        st.caption(
            f"{len(job_text.strip()):,} characters · the full offer gives more reliable extraction and matching"
        )
        analyze = st.button(
            "Analyze offer and prepare draft",
            type="primary",
            use_container_width=True,
            disabled=len(job_text.strip()) < 40,
            key="premium_analyze_offer",
        )

    if analyze:
        with st.status(
            "Understanding the offer and retrieving verified evidence…",
            expanded=True,
        ) as status:
            try:
                st.write("Extracting role requirements")
                results = _run_pipeline(user_id, candidate_name, job_text)
                st.session_state["results"] = results
                st.write("Ranking verified profile evidence")
                st.write("Composing the grounded email")
                status.update(
                    label="Application workspace ready",
                    state="complete",
                    expanded=False,
                )
            except UsageQuotaExceeded as exc:
                status.update(
                    label="Daily AI quota reached",
                    state="error",
                )
                st.warning(str(exc))
            except Exception as exc:
                status.update(
                    label="The analysis could not be completed",
                    state="error",
                )
                st.error(
                    f"JobCopilot could not complete this analysis ({type(exc).__name__}). "
                    "Check the offer, provider configuration and profile, then try again."
                )

    results = st.session_state.get("results")
    if not results:
        st.markdown(
            """
            <div class="jc-card" style="margin-top:1rem;text-align:center;padding:2rem">
              <div class="jc-card-title">Your application workspace will appear here</div>
              <p class="jc-muted">You will review the role, matching evidence, email and next actions before anything leaves JobCopilot.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    analysis = results["job_analysis"]
    match = results["match"]
    draft = results["email_draft"]
    events = results.get("llm_telemetry", [])
    claims = draft.get("claim_evidence", [])
    memory_records = results.get("retrieved_memory_records", [])

    st.markdown(
        f"""
        <div class="jc-hero" style="margin-top:1.25rem">
          <div class="jc-eyebrow">Application workspace</div>
          <h1>{escape(str(analysis.get('role', 'Unknown role')))}</h1>
          <p>{escape(str(analysis.get('company', 'Unknown company')))} · {escape(str(analysis.get('location', 'Unknown location')))} · {escape(str(analysis.get('contract_type', 'Unknown contract')))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_compact_ai_status(events, len(claims))

    overview_tab, match_tab, email_tab = st.tabs(
        ["Role overview", "Match & evidence", "Email & actions"]
    )
    with overview_tab:
        _render_role_overview(analysis)
    with match_tab:
        _render_match_and_evidence(match, draft, memory_records)
    with email_tab:
        _render_email_actions(user_id, analysis, draft)

    _render_technical_trace(events)
