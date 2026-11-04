"""Unstable-area classification, evaluated scenario by scenario.

Task: from the bus voltage deviations seen in the first few post-fault
snapshots, say which of the 10 areas are unstable (multi-label, 0 to 2 areas
per scenario).

With 56 scenarios the only honest protocol is leave-one-scenario-out: every
prediction comes from a model that never saw any row of that scenario.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .config import AREAS
from .data import AREA_COLS, V_COLS, post_fault

POST_TIMES = [2.0, 2.02, 2.04, 2.06, 2.08, 2.1]


def scenario_features(df: pd.DataFrame, window: int = len(POST_TIMES)) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mean, max and spread of each bus's voltage deviation over the first ``window`` snapshots.

    Exact duplicate scenarios are dropped so a held-out scenario never has a twin in training.
    """
    post = modelling_rows(post_fault(df))
    post = post[post["t"] <= POST_TIMES[window - 1] + 1e-9]
    g = post.groupby("sim")[V_COLS]
    feats = [g.mean().add_suffix("_mean"), g.max().add_suffix("_max")]
    if window > 1:
        feats.append(g.std().add_suffix("_std"))
    X = pd.concat(feats, axis=1).fillna(0.0)
    Y = post.groupby("sim")[AREA_COLS].max().loc[X.index]
    return X, Y


def modelling_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop simulations that are byte-for-byte copies of another file."""
    return df[df["duplicate_of"] == 0] if "duplicate_of" in df else df


class MajorityLabels(BaseEstimator, ClassifierMixin):
    """Predict each area's most common state (always 'stable' here)."""

    def fit(self, X, Y):
        self.labels_ = (np.asarray(Y).mean(axis=0) > 0.5).astype(int)
        return self

    def predict(self, X):
        return np.tile(self.labels_, (len(X), 1))

    def predict_proba_matrix(self, X):
        return np.tile(self.labels_.astype(float), (len(X), 1))


def candidate_models() -> dict[str, BaseEstimator]:
    return {
        "Majority (always stable)": MajorityLabels(),
        "Logistic regression": make_pipeline(
            StandardScaler(),
            MultiOutputClassifier(LogisticRegression(C=1.0, max_iter=5000, class_weight="balanced")),
        ),
        "Random forest": RandomForestClassifier(n_estimators=400, class_weight="balanced", random_state=0, n_jobs=1),
    }


def unstable_probability(model, X) -> np.ndarray:
    """P(unstable) per area as an (n, 10) matrix, whatever the estimator type."""
    if isinstance(model, MajorityLabels):
        return model.predict_proba_matrix(X)
    proba = model.predict_proba(X)
    cols = []
    for p in proba:
        cols.append(p[:, 1] if p.shape[1] == 2 else np.zeros(len(X)))
    return np.column_stack(cols)


def multilabel_scores(Y: np.ndarray, P: np.ndarray) -> dict:
    Y, P = np.asarray(Y), np.asarray(P)
    return {
        "micro_f1": float(f1_score(Y, P, average="micro", zero_division=0)),
        "macro_f1": float(f1_score(Y, P, average="macro", zero_division=0)),
        "exact_match": float((Y == P).all(axis=1).mean()),
        "area_accuracy": float((Y == P).mean()),
        "per_area_f1": [float(f1_score(Y[:, i], P[:, i], zero_division=0)) for i in range(Y.shape[1])],
    }


def leave_one_scenario_out(model, X: pd.DataFrame, Y: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Out-of-scenario predictions and probabilities for every simulation."""
    Xv, Yv = X.to_numpy(), Y.to_numpy()
    P = np.zeros_like(Yv)
    proba = np.zeros(Yv.shape, dtype=float)
    for i in range(len(Xv)):
        train = np.arange(len(Xv)) != i
        m = clone(model).fit(Xv[train], Yv[train])
        P[i] = m.predict(Xv[i : i + 1])[0]
        proba[i] = unstable_probability(m, Xv[i : i + 1])[0]
    return P, proba


# The accuracy trap -----------------------------------------------------------


def system_class(df: pd.DataFrame) -> pd.Series:
    """The original notebook's 12-class target: 0 stable, 1-10 one area, 11 several."""
    n = df[AREA_COLS].sum(axis=1)
    single = df[AREA_COLS].to_numpy().argmax(axis=1) + 1
    return pd.Series(np.where(n == 0, 0, np.where(n == 1, single, 11)), index=df.index)


def accuracy_trap(df: pd.DataFrame, seed: int = 42) -> dict:
    """Reproduce the headline-accuracy pattern of the original notebook, then remove it.

    1. All rows (pre-fault included), random row split: accuracy looks high
       because the majority of rows are steady-state copies labelled stable.
    2. Same model, whole scenarios held out.
    """
    df = modelling_rows(df)
    X = df[V_COLS].fillna(0).to_numpy()
    y = system_class(df).to_numpy()
    rf = RandomForestClassifier(n_estimators=300, random_state=seed, n_jobs=1)

    tr, te = train_test_split(np.arange(len(df)), test_size=0.2, random_state=seed)
    rf.fit(X[tr], y[tr])
    p = rf.predict(X[te])
    random_rows = {
        "accuracy": float(accuracy_score(y[te], p)),
        "macro_f1": float(f1_score(y[te], p, average="macro", zero_division=0)),
        "share_stable": float((y[te] == 0).mean()),
    }

    gss = GroupShuffleSplit(n_splits=20, test_size=0.2, random_state=seed)
    accs, f1s = [], []
    for tr, te in gss.split(X, y, groups=df["sim"]):
        m = clone(rf).fit(X[tr], y[tr])
        p = m.predict(X[te])
        unstable = y[te] != 0
        accs.append(accuracy_score(y[te], p))
        f1s.append(f1_score(y[te][unstable], p[unstable], average="macro", zero_division=0))
    held_out = {
        "accuracy": float(np.mean(accs)),
        "macro_f1_unstable_rows": float(np.mean(f1s)),
    }
    return {
        "rows": len(df),
        "share_stable_rows": float((y == 0).mean()),
        "random_row_split": random_rows,
        "scenario_split": held_out,
        "original_notebook": {"accuracy": 0.933, "macro_f1": 0.12, "regressor_r2": 0.535},
    }


AREA_NAMES = [f"Area {a}" for a in AREAS]
