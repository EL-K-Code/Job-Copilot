from __future__ import annotations

import streamlit as st

from app.config import settings
from app.services.google_oauth import (
    exchange_google_oauth_callback,
    verify_signed_oauth_state,
)


def handle_google_oauth_callback() -> None:
    """Complete hosted Google OAuth only after the same beta user is authenticated."""
    if not settings.hosted_google_oauth_enabled:
        return

    error = str(st.query_params.get("error", "")).strip()
    code = str(st.query_params.get("code", "")).strip()
    state = str(st.query_params.get("state", "")).strip()
    if not error and not code:
        return

    if error:
        st.query_params.clear()
        st.error("Google authorization was cancelled or denied. You can try connecting again.")
        st.stop()

    try:
        state_user_id = verify_signed_oauth_state(state)
    except Exception as exc:
        st.query_params.clear()
        st.error(f"Google connection could not be completed ({type(exc).__name__}).")
        st.caption("Return to Settings and start the Google connection again.")
        st.stop()

    current_user = st.session_state.get("authenticated_user") or {}
    current_user_id = str(current_user.get("user_id", "")).strip().casefold()

    if not current_user_id:
        st.info(
            "Sign in to JobCopilot to finish connecting Google. "
            "The authorization will only be accepted for the same private-beta account that started it."
        )
        return

    if current_user_id != state_user_id:
        st.query_params.clear()
        st.error("This Google authorization belongs to a different JobCopilot account.")
        st.caption("Sign out and restart the Google connection from the correct account.")
        st.stop()

    try:
        exchanged_user_id = exchange_google_oauth_callback(code, state)
        if exchanged_user_id != current_user_id:
            raise RuntimeError("Google OAuth callback tenant mismatch.")
    except Exception as exc:
        st.query_params.clear()
        st.error(f"Google connection could not be completed ({type(exc).__name__}).")
        st.caption("Return to Settings and start the Google connection again.")
        st.stop()

    st.session_state["google_oauth_flash"] = "Google connected successfully."
    st.query_params.clear()
    st.rerun()
