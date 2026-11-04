"""Evaluate the unstable-area classifiers and save metrics for the app.

    python scripts/train_models.py

Every score is leave-one-scenario-out. Writes models/metrics.json,
models/loso_predictions.parquet and the final model fitted on all scenarios.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.base import clone  # noqa: E402

from src.config import LONG_PATH, METRICS_PATH, MODEL_DIR, MODEL_PATH, PREDICTIONS_PATH  # noqa: E402
from src.data import AREA_COLS  # noqa: E402
from src.model import (  # noqa: E402
    POST_TIMES,
    accuracy_trap,
    candidate_models,
    leave_one_scenario_out,
    multilabel_scores,
    scenario_features,
)

BEST = "Logistic regression"


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(LONG_PATH)
    suspect = set(df.loc[df.label_suspect == 1, "sim"].unique())

    X, Y = scenario_features(df)
    keep = ~X.index.isin(suspect)
    models = candidate_models()
    results, preds = {}, {}
    for name, model in models.items():
        P, proba = leave_one_scenario_out(model, X, Y)
        preds[name] = (P, proba)
        clean = leave_one_scenario_out(model, X[keep], Y[keep])[0]
        results[name] = {
            "all": multilabel_scores(Y.to_numpy(), P),
            "without_suspect": multilabel_scores(Y[keep].to_numpy(), clean),
        }
        s = results[name]["all"]
        print(f"{name:26s} micro-F1 {s['micro_f1']:.3f}  macro-F1 {s['macro_f1']:.3f}  exact {s['exact_match']:.3f}")

    # Observation window: how many post-fault snapshots does the model need?
    windows = []
    for w in range(1, len(POST_TIMES) + 1):
        Xw, Yw = scenario_features(df, window=w)
        P, _ = leave_one_scenario_out(models[BEST], Xw, Yw)
        s = multilabel_scores(Yw.to_numpy(), P)
        windows.append({"window": w, "ms_after_fault": round((POST_TIMES[w - 1] - 2.0) * 1000), **s})
        print(f"  window {w} ({windows[-1]['ms_after_fault']:>3} ms)  micro-F1 {s['micro_f1']:.3f}")

    trap = accuracy_trap(df)
    print(
        f"Accuracy trap: random rows acc {trap['random_row_split']['accuracy']:.3f} "
        f"(macro-F1 {trap['random_row_split']['macro_f1']:.3f}); held-out scenarios acc "
        f"{trap['scenario_split']['accuracy']:.3f}, unstable-row macro-F1 {trap['scenario_split']['macro_f1_unstable_rows']:.3f}"
    )

    P, proba = preds[BEST]
    rows = []
    for i, sim in enumerate(X.index):
        for j in range(len(AREA_COLS)):
            rows.append(
                {
                    "sim": int(sim),
                    "area": j + 1,
                    "truth": int(Y.iloc[i, j]),
                    "pred": int(P[i, j]),
                    "p_unstable": float(proba[i, j]),
                }
            )
    pd.DataFrame(rows).to_parquet(PREDICTIONS_PATH, index=False)

    final = clone(models[BEST]).fit(X.to_numpy(), Y.to_numpy())
    joblib.dump({"model": final, "features": list(X.columns), "name": BEST}, MODEL_PATH)

    metrics = {
        "protocol": "leave-one-scenario-out",
        "n_scenarios": int(len(X)),
        "suspect_sims": sorted(int(s) for s in suspect if s in X.index),
        "duplicate_sims": sorted(int(s) for s in df.loc[df.duplicate_of > 0, "sim"].unique()),
        "best": BEST,
        "models": results,
        "windows": windows,
        "accuracy_trap": trap,
        "label_base_rate": float(np.asarray(Y).mean()),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    print(f"Saved {METRICS_PATH.name}, {PREDICTIONS_PATH.name}, {MODEL_PATH.name}")


if __name__ == "__main__":
    main()
