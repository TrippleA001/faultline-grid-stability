from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import DESIGN, IEEE39_LOAD_MW, LOAD_BUSES, RAW_DIR  # noqa: E402
from src.data import AREA_COLS, NUMERIC_COLS, build, canonical_columns  # noqa: E402


@pytest.fixture(scope="module")
def built():
    if not any(RAW_DIR.glob("Power System *.csv")):
        pytest.skip("raw simulation CSVs not present")
    return build()


def test_design_enumeration_covers_every_pair_once():
    assert len(DESIGN) == 56
    assert DESIGN[1] == ()
    pairs = [v for v in DESIGN.values() if len(v) == 2]
    assert len(pairs) == len(set(pairs)) == 45
    assert DESIGN[12] == (1, 2) and DESIGN[56] == (1, 10)


def test_canonical_columns_match_raw_width():
    assert len(canonical_columns()) == 125


def test_shape_and_types(built):
    df, audit = built
    assert audit["files"] == 56
    assert df.sim.nunique() == 56
    assert df[NUMERIC_COLS].dtypes.map(lambda d: np.issubdtype(d, np.floating)).all()
    assert set(np.unique(df[AREA_COLS])) <= {0, 1}


def test_pre_fault_is_steady_after_repair(built):
    df, _ = built
    pre = df[df.t <= 1.98]
    distinct = pre.groupby("sim")[NUMERIC_COLS].apply(lambda g: len(g.drop_duplicates()))
    assert (distinct == 1).all()


def test_fill_series_artefact_detected(built):
    _, audit = built
    keys = {i["key"] for i in audit["issues"]}
    assert "fill_series" in keys


def test_base_loads_match_ieee39(built):
    df, _ = built
    first = df.iloc[0]
    for b in LOAD_BUSES:
        assert first[f"p_{b}"] == pytest.approx(IEEE39_LOAD_MW[b])


def test_suspect_labels(built):
    _, audit = built
    assert audit["suspect_sims"] == [5, 30, 47, 48, 51]


def test_duplicate_file_detected(built):
    df, audit = built
    assert audit["duplicate_sims"] == [5]
    assert (df.loc[df.sim == 5, "duplicate_of"] == 4).all()
