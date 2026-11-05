"""Cached loaders for the Streamlit pages."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from .config import AUDIT_PATH, LONG_PATH, METRICS_PATH, PREDICTIONS_PATH


@st.cache_data(show_spinner=False)
def load_simulations() -> pd.DataFrame:
    return pd.read_parquet(LONG_PATH)


@st.cache_data(show_spinner=False)
def load_audit() -> dict:
    return json.loads(AUDIT_PATH.read_text())


@st.cache_data(show_spinner=False)
def load_metrics() -> dict:
    return json.loads(METRICS_PATH.read_text())


@st.cache_data(show_spinner=False)
def load_predictions() -> pd.DataFrame:
    return pd.read_parquet(PREDICTIONS_PATH)


def scenario_name(sim: int, recorded: str) -> str:
    areas = recorded.replace(",", " + ") if recorded else "none"
    return f"Sim {sim} · unstable: {'Area ' + areas if recorded else 'none (base case)'}"
