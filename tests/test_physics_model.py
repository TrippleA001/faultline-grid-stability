from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import LOAD_BUSES, RAW_DIR  # noqa: E402
from src.data import build  # noqa: E402
from src.model import (  # noqa: E402
    MajorityLabels,
    leave_one_scenario_out,
    multilabel_scores,
    scenario_features,
    system_class,
)
from src.physics import r2, rule_scores  # noqa: E402


@pytest.fixture(scope="module")
def df():
    if not any(RAW_DIR.glob("Power System *.csv")):
        pytest.skip("raw simulation CSVs not present")
    return build()[0]


def test_r2_perfect_and_constant():
    y = np.array([1.0, 2.0, 3.0])
    assert r2(y, y) == pytest.approx(1.0)
    assert np.isnan(r2(np.ones(3), np.ones(3)))


def test_shedding_rule_reproduces_data(df):
    scores = rule_scores(df)
    assert scores["r2_lsf_x_load"] > 0.99
    assert 0.75 < scores["median_gain"] < 0.85


def test_scenario_features_one_row_per_sim(df):
    X, Y = scenario_features(df)
    assert len(X) == len(Y) == 55  # the exact duplicate (sim 5) is dropped
    assert 5 not in X.index
    assert X.shape[1] == 3 * len(LOAD_BUSES)
    assert not X.isna().any().any()
    X1, _ = scenario_features(df, window=1)
    assert X1.shape[1] == 2 * len(LOAD_BUSES)


def test_loso_never_trains_on_test_scenario():
    class Spy(MajorityLabels):
        seen: list[int] = []

        def fit(self, X, Y):
            Spy.seen.append(len(X))
            return super().fit(X, Y)

    X = pd.DataFrame(np.arange(10).reshape(5, 2))
    Y = pd.DataFrame(np.zeros((5, 3), dtype=int))
    P, proba = leave_one_scenario_out(Spy(), X, Y)
    assert Spy.seen == [4] * 5
    assert P.shape == proba.shape == (5, 3)


def test_multilabel_scores_all_stable_baseline():
    Y = np.array([[1, 0], [0, 0], [0, 1]])
    P = np.zeros_like(Y)
    s = multilabel_scores(Y, P)
    assert s["micro_f1"] == 0.0
    assert s["exact_match"] == pytest.approx(1 / 3)


def test_system_class_codes():
    frame = pd.DataFrame({f"area_{a}": [0, 0, 0] for a in range(1, 11)})
    frame.loc[1, "area_4"] = 1
    frame.loc[2, ["area_2", "area_7"]] = 1
    assert system_class(frame).tolist() == [0, 4, 11]
