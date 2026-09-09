from __future__ import annotations

import streamlit as st

from app.auth import load_beta_users
from app.config import settings
from app.services.google_oauth import exchange_google_oauth_callback


def handle_google_oauth_callback() -> None:
    """Complete a hosted Google OAuth callback before the normal beta login gate."""
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
        user_id = exchange_google_oauth_callback(code, state)
        user = load_beta_users().get(user_id)
        if not user or not user.get("enabled", True):
            raise RuntimeError("The private beta account bound to this OAuth flow is disabled.")
    except Exception as exc:
        st.query_params.clear()
        st.error(f"Google connection could not be completed ({type(exc).__name__}).")
        st.caption("Return to Settings and start the Google connection again.")
        st.stop()

    st.session_state["authenticated_user"] = {
        "user_id": user_id,
        "display_name": str(user.get("display_name", user_id)),
    }
    st.session_state["google_oauth_flash"] = "Google connected successfully."
    st.query_params.clear()
    st.rerun()
