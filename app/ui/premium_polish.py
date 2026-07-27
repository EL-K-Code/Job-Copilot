from __future__ import annotations

import streamlit as st


POLISH_CSS = """
<style>
.jc-trust-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .35rem;
  margin: -.25rem 0 1rem;
}
.jc-evidence-fact {
  margin-top: .65rem;
  padding: .72rem .85rem;
  border: 1px solid #dfe7f5;
  border-left: 3px solid #315efb;
  border-radius: 10px;
  background: #f8faff;
  color: #26354f;
  line-height: 1.5;
}
.stButton > button:disabled,
[data-testid="stFormSubmitButton"] > button:disabled {
  color: #8b95a7 !important;
  background: #e9edf4 !important;
  border: 1px solid #dde3ed !important;
  box-shadow: none !important;
  opacity: 1 !important;
}
[data-testid="stFileUploaderDropzone"] {
  border-radius: 14px;
  border-color: #dbe3f0;
  background: #f8faff;
}
[data-testid="stExpander"] {
  border-color: #dfe5ef;
  border-radius: 12px;
}
[data-testid="stDataFrame"] {
  border-radius: 12px;
  overflow: hidden;
}
</style>
"""


def inject_premium_polish() -> None:
    st.markdown(POLISH_CSS, unsafe_allow_html=True)
