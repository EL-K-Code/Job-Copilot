from __future__ import annotations

import hashlib
from html import escape

import streamlit as st


_OUTPUT_LABELS = {
    "cv_tailoring": "CV tailoring",
    "ats_answers": "ATS answers",
    "cover_letter": "Cover letter",
    "recruiter_message": "Recruiter message",
    "application_email": "Application email",
    "interview_prep": "Interview preparation",
}

_CHANNEL_BADGES = {
    "ats_portal": "ATS / portal",
    "email": "Email",
    "linkedin": "LinkedIn",
    "academic": "Academic",
    "unknown": "Route not stated",
}


def _editor_key(prefix: str, title: str, text: str) -> str:
    digest = hashlib.sha256(f"{title}|{text}".encode("utf-8")).hexdigest()[:12]
    return f"application_pack:{prefix}:{digest}"


def _editable_text(label: str, text: str, *, prefix: str, height: int) -> None:
    key = _editor_key(prefix, label, text)
    if key not in st.session_state:
        st.session_state[key] = text
    st.text_area(label, key=key, height=height)


def _render_claim_evidence(claim: dict, memory_records: list[dict]) -> None:
    by_id = {
        str(record.get("id", "")): record
        for record in memory_records
        if str(record.get("id", ""))
    }
    supporting = [
        by_id[memory_id]
        for memory_id in claim.get("supporting_memory_ids", [])
        if memory_id in by_id
    ]
    with st.expander("Verified evidence"):
        for record in supporting:
            st.write(f"• {record.get('content', '')}")
        aligned = claim.get("aligned_job_terms", [])
        if aligned:
            st.caption("Aligned with: " + ", ".join(str(item) for item in aligned))


def render_application_pack(pack: dict, memory_records: list[dict]) -> None:
    """Render the channel-aware application pack without generating new candidate facts."""

    channel = str(pack.get("channel", "unknown"))
    route_label = str(pack.get("route_label", "Application route not stated"))
    outputs = [str(item) for item in pack.get("recommended_outputs", [])]
    badge = _CHANNEL_BADGES.get(channel, _CHANNEL_BADGES["unknown"])
    pills = " ".join(
        f'<span class="jc-pill">{escape(_OUTPUT_LABELS.get(item, item.replace("_", " ").title()))}</span>'
        for item in outputs
    )

    st.markdown(
        f"""
        <div class="jc-card">
          <div class="jc-eyebrow">Recommended application route</div>
          <div class="jc-card-title">{escape(route_label)}</div>
          <div class="jc-trust-row">
            <span class="jc-pill jc-pill-success">{escape(badge)}</span>
            {pills}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if channel == "unknown":
        st.info(
            "The offer does not state how to apply. JobCopilot prepared the safest reusable "
            "outputs, but you should confirm the route on the employer's page."
        )

    cv_tab, ats_tab, letter_tab, recruiter_tab, interview_tab = st.tabs(
        [
            "CV tailoring",
            "ATS answers",
            "Cover letter",
            "Recruiter outreach",
            "Interview prep",
        ]
    )

    with cv_tab:
        st.markdown("#### Verified points to emphasize")
        highlights = pack.get("cv_highlights", [])
        for index, claim in enumerate(highlights, start=1):
            with st.container(border=True):
                st.markdown(f"**{index}. {claim.get('claim', '')}**")
                _render_claim_evidence(claim, memory_records)

        st.markdown("#### Terms to review — not candidate skills")
        missing = pack.get("missing_job_terms", [])
        if missing:
            st.warning(
                "These terms are explicit in the offer but are not covered by the selected "
                "verified evidence. Do not add them to the CV unless they are genuinely true."
            )
            st.markdown(
                " ".join(
                    f'<span class="jc-pill">{escape(str(item))}</span>'
                    for item in missing
                ),
                unsafe_allow_html=True,
            )
        else:
            st.success("No uncovered term was found in the selected offer evidence.")

    with ats_tab:
        answers = pack.get("ats_answers", [])
        if "ats_answers" not in outputs:
            st.caption("ATS answers are optional for the detected route.")
        for index, item in enumerate(answers, start=1):
            _editable_text(
                str(item.get("title", f"ATS answer {index}")),
                str(item.get("text", "")),
                prefix=f"ats-{index}",
                height=190,
            )

    with letter_tab:
        if "cover_letter" not in outputs:
            st.caption("A cover letter was not explicitly required; use it only when useful.")
        letter = pack.get("cover_letter", {})
        _editable_text(
            str(letter.get("title", "Cover letter")),
            str(letter.get("text", "")),
            prefix="cover-letter",
            height=420,
        )

    with recruiter_tab:
        if "recruiter_message" not in outputs:
            st.caption("Recruiter outreach is optional for the detected route.")
        message = pack.get("recruiter_message", {})
        _editable_text(
            str(message.get("title", "Recruiter message")),
            str(message.get("text", "")),
            prefix="recruiter-message",
            height=180,
        )

    with interview_tab:
        questions = pack.get("interview_questions", [])
        if questions:
            for index, question in enumerate(questions, start=1):
                st.markdown(f"**{index}.** {question}")
        else:
            st.caption("No interview question could be derived from the explicit offer details.")
