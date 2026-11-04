"""The engineer's load-shedding rule, written down as code.

The PSS/E study sizes shedding at each load bus in two steps:

1. a load-shedding factor proportional to the bus voltage deviation,
   LSF ~= k * dV with k ~= 0.8, and
2. shed P (Q) = LSF * base-case load P (Q).

The original notebook trained an LSTM to predict the 38 shed P/Q values.
Step 2 is exact arithmetic, so the rule is the right baseline for any learned
model, and it is what the app uses to report megawatts shed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import IEEE39_LOAD_MW, LOAD_BUSES, LSF_GAIN
from .data import post_fault


def r2(y: np.ndarray, yhat: np.ndarray) -> float:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    ok = ~(np.isnan(y) | np.isnan(yhat))
    y, yhat = y[ok], yhat[ok]
    ss_tot = ((y - y.mean()) ** 2).sum()
    return float(1 - ((y - yhat) ** 2).sum() / ss_tot) if ss_tot > 0 else float("nan")


def base_loads(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Base-case active load per monitored bus.

    Taken from the IEEE 39-bus reference, which the audit confirms the export
    matches exactly. Reading it from the data instead would be fragile: after a
    fault the LOAD P columns hold a different quantity.
    """
    return pd.DataFrame({"bus": LOAD_BUSES, "p_mw": [IEEE39_LOAD_MW[b] for b in LOAD_BUSES]})


def shed_from_rule(df: pd.DataFrame, gain: float | None = None) -> pd.DataFrame:
    """Shed P per bus predicted by the rule.

    With ``gain=None`` the recorded LSF is used (step 2 only). With a gain the
    LSF itself is rebuilt from voltage deviation (steps 1 and 2).
    """
    base = base_loads(df).set_index("bus")
    out = pd.DataFrame(index=df.index)
    for b in LOAD_BUSES:
        lsf = df[f"lsf_{b}"] if gain is None else gain * df[f"v_{b}"].clip(lower=0)
        out[f"shed_p_{b}"] = lsf * base.at[b, "p_mw"]
    return out


def plausible(df: pd.DataFrame) -> pd.DataFrame:
    """True where a bus reading is physically possible: 0 <= LSF <= 1 and shed P <= base load."""
    base = base_loads(df).set_index("bus")
    return pd.DataFrame(
        {b: df[f"lsf_{b}"].between(0, 1) & (df[f"shed_p_{b}"] <= base.at[b, "p_mw"] + 1e-6) for b in LOAD_BUSES},
        index=df.index,
    )


def fit_gain(df: pd.DataFrame) -> dict[int, float]:
    """Least-squares LSF/dV gain per bus over post-fault rows with a real deviation."""
    post = post_fault(df)
    gains = {}
    for b in LOAD_BUSES:
        v, lsf = post[f"v_{b}"], post[f"lsf_{b}"]
        ok = (v > 0.01) & lsf.between(0, 1)
        gains[b] = float((v[ok] * lsf[ok]).sum() / (v[ok] ** 2).sum()) if ok.any() else float("nan")
    return gains


def rule_scores(df: pd.DataFrame) -> dict:
    """How well the rule reproduces the recorded shedding, per bus and overall."""
    post = post_fault(df)
    exact = shed_from_rule(post)
    from_v = shed_from_rule(post, gain=LSF_GAIN)
    ok = plausible(post)
    per_bus = []
    for b in LOAD_BUSES:
        y = post[f"shed_p_{b}"].to_numpy()
        m = ok[b].to_numpy()
        per_bus.append(
            {
                "bus": b,
                "r2_lsf_x_load": r2(y, exact[f"shed_p_{b}"].to_numpy()),
                "r2_lsf_x_load_plausible": r2(y[m], exact[f"shed_p_{b}"].to_numpy()[m]),
                "r2_from_voltage": r2(y[m], from_v[f"shed_p_{b}"].to_numpy()[m]),
                "implausible_cells": int((~m).sum()),
            }
        )
    cols = [f"shed_p_{b}" for b in LOAD_BUSES]
    y_all = post[cols].to_numpy().ravel()
    mask = ok[LOAD_BUSES].to_numpy().ravel()
    gains = fit_gain(df)
    return {
        "r2_lsf_x_load_all": r2(y_all, exact[cols].to_numpy().ravel()),
        "r2_lsf_x_load": r2(y_all[mask], exact[cols].to_numpy().ravel()[mask]),
        "r2_from_voltage": r2(y_all[mask], from_v[cols].to_numpy().ravel()[mask]),
        "implausible_cells": int((~mask).sum()),
        "median_gain": float(np.nanmedian(list(gains.values()))),
        "gains": {str(k): v for k, v in gains.items()},
        "per_bus": per_bus,
    }


def total_shed(df: pd.DataFrame) -> pd.DataFrame:
    """Total recorded MW shed per simulation and time step (post-fault), impossible readings left out."""
    post = post_fault(df)
    return post[["sim", "t"]].assign(shed_mw=plausible_shed(post).sum(axis=1, min_count=1))


def plausible_shed(df: pd.DataFrame) -> pd.DataFrame:
    """Recorded shed P per bus (columns = bus numbers), NaN where the reading is physically impossible."""
    ok = plausible(df)
    return pd.DataFrame({b: df[f"shed_p_{b}"].where(ok[b]) for b in LOAD_BUSES}, index=df.index)
