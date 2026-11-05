"""Faultline: IEEE 39-bus stability and load-shedding lab.

Streamlit entry point. Configures the page, injects the theme and wires up
`st.navigation` across five pages.

Run locally:

    streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

from src.theme import inject_css  # noqa: E402

st.set_page_config(
    page_title="Faultline · IEEE 39-bus Stability Lab",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="auto",
)

inject_css()

PAGES = [
    st.Page("pages/1_overview.py", title="Overview", icon=":material/bolt:", default=True),
    st.Page("pages/2_grid_explorer.py", title="Grid Explorer", icon=":material/hub:"),
    st.Page("pages/3_load_shedding.py", title="Load Shedding", icon=":material/electric_meter:"),
    st.Page("pages/4_model_lab.py", title="Model Lab", icon=":material/psychology:"),
    st.Page("pages/5_data_audit.py", title="Data Audit", icon=":material/fact_check:"),
]

pg = st.navigation(PAGES, position="sidebar")
pg.run()
