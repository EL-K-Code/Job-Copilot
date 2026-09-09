from __future__ import annotations

import streamlit as st

from app.auth import authenticate_beta_user
from app.config import settings
from app.tenancy import DEFAULT_LOCAL_USER_ID


def authenticated_user() -> dict[str, str] | None:
    """Authenticate a hosted recruiter-demo tester without exposing local-only features."""
    if not settings.beta_auth_enabled:
        return {
            "user_id": DEFAULT_LOCAL_USER_ID,
            "display_name": settings.local_candidate_name or "Local demo",
        }

    current = st.session_state.get("authenticated_user")
    if current:
        return current

    _, center, _ = st.columns([1, 1.15, 1])
    with center:
        st.markdown(
            """
            <div class="jc-hero" style="margin-top:4rem;text-align:center">
              <div class="jc-eyebrow">Hosted recruiter demo</div>
              <h1>JobCopilot</h1>
              <p>Evidence-grounded AI for job applications, with a persistent private workspace.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("hosted-beta-login"):
            st.markdown("### Access the demo")
            user_id = st.text_input("User ID", placeholder="recruiter-demo")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button(
                "Sign in securely",
                type="primary",
                use_container_width=True,
            )
        st.caption(
            "Verified profile facts, tracker state and AI quota usage are isolated per tester. "
            "Raw CV uploads are not persisted."
        )

    if submitted:
        try:
            user = authenticate_beta_user(user_id, password)
        except Exception as exc:
            st.error(str(exc))
            return None
        if user is None:
            st.error("Invalid or disabled private beta account.")
            return None
        st.session_state["authenticated_user"] = user
        st.rerun()
    return None
