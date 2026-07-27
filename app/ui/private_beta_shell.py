from __future__ import annotations

import streamlit as st

from app.config import settings
from app.tenancy import ensure_user_directories
from app.tools.gmail_tools import google_token_exists
from app.ui import premium_private_beta as premium
from app.ui.application_workspace import render_application_workspace
from app.ui.premium_polish import inject_premium_polish
from app.ui.profile_workspace import render_profile_gate, render_profile_page


NAV_ITEMS = [
    "Overview",
    "Profile",
    "New application",
    "Agent Chat",
    "Applications",
    "Settings",
]


def _render_sidebar(user: dict[str, str]) -> str:
    pending = st.session_state.pop("pending_nav_page", None)
    if pending in NAV_ITEMS:
        st.session_state["nav_radio"] = pending

    with st.sidebar:
        st.markdown(
            '<div class="jc-brand">JobCopilot<span class="jc-brand-dot">.</span></div>',
            unsafe_allow_html=True,
        )
        st.caption("Private beta workspace")
        st.divider()
        page = st.radio(
            "Navigation",
            NAV_ITEMS,
            key="nav_radio",
            label_visibility="collapsed",
        )
        st.divider()
        st.write(f"**{user['display_name']}**")
        st.caption(f"Workspace: {user['user_id']}")
        if google_token_exists(user["user_id"]):
            st.success("Google connected")
        else:
            st.info("Google not connected")
        if settings.beta_auth_enabled and st.button(
            "Sign out",
            use_container_width=True,
        ):
            premium._logout()
    return page


def main() -> None:
    st.set_page_config(
        page_title="JobCopilot Private Beta",
        page_icon="✦",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    premium._inject_theme()
    inject_premium_polish()

    user = premium._authenticated_user()
    if user is None:
        st.stop()

    user_id = user["user_id"]
    ensure_user_directories(user_id)
    premium._initialize_agent_session(user_id)

    if not render_profile_gate(user_id):
        st.stop()

    page = _render_sidebar(user)
    if page == "Overview":
        premium._render_overview(user)
    elif page == "Profile":
        render_profile_page(user_id)
    elif page == "New application":
        render_application_workspace(user_id)
    elif page == "Agent Chat":
        premium._render_agent_chat(user_id)
    elif page == "Applications":
        premium._render_applications(user_id)
    else:
        premium._render_settings(user_id)
