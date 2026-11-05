"""Smoke tests: every page renders without an exception."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed" / "simulations.parquet"
METRICS = ROOT / "models" / "metrics.json"

pytestmark = pytest.mark.skipif(
    not (PROCESSED.exists() and METRICS.exists()), reason="run the build and training scripts first"
)


def test_entrypoint_renders_overview():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    assert not at.exception


@pytest.mark.parametrize("page", ["2_grid_explorer", "3_load_shedding", "4_model_lab", "5_data_audit"])
def test_page_renders(page):
    at = AppTest.from_file(str(ROOT / "pages" / f"{page}.py"), default_timeout=180).run()
    assert not at.exception


@pytest.mark.parametrize("sim", [1, 5, 47])
def test_grid_explorer_edge_scenarios(sim):
    """Base case, the duplicated file (no model prediction) and a suspect scenario."""
    at = AppTest.from_file(str(ROOT / "pages" / "2_grid_explorer.py"), default_timeout=180).run()
    at.selectbox[0].set_value(sim).run()
    assert not at.exception
