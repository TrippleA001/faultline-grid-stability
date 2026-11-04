"""Load, clean and audit the PSS/E load-shedding simulations.

Each raw CSV is one fault scenario on the IEEE 39-bus system: 102 time steps
(0.02 s to 2.10 s) by 125 columns. The headers carry typos and inconsistent
spacing ("BUS 26LOAD Q", "ARA 4 CONDITION", "SHEDDING AT BUS 20P2"), so columns
are mapped by position and each position is checked against the bus number it
should carry.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .config import AREAS, DESIGN, IEEE39_LOAD_MW, LOAD_BUSES, PRE_FAULT_END, RAW_DIR, SIM_GLOB

# Canonical column groups -----------------------------------------------------
V_COLS = [f"v_{b}" for b in LOAD_BUSES]
P_COLS = [f"p_{b}" for b in LOAD_BUSES]
Q_COLS = [f"q_{b}" for b in LOAD_BUSES]
LSF_COLS = [f"lsf_{b}" for b in LOAD_BUSES]
SHED_P_COLS = [f"shed_p_{b}" for b in LOAD_BUSES]
SHED_Q_COLS = [f"shed_q_{b}" for b in LOAD_BUSES]
AREA_COLS = [f"area_{a}" for a in AREAS]
NUMERIC_COLS = V_COLS + P_COLS + Q_COLS + LSF_COLS + SHED_P_COLS + SHED_Q_COLS


def canonical_columns() -> list[str]:
    """Canonical names in the raw column order."""
    cols = ["t", *V_COLS]
    for b in LOAD_BUSES:
        cols += [f"p_{b}", f"q_{b}"]
    for b in LOAD_BUSES:
        cols += [f"lsf_{b}", f"shed_p_{b}", f"shed_q_{b}"]
    return cols + AREA_COLS


@dataclass
class Issue:
    """One data-quality finding, written to the audit report."""

    key: str
    title: str
    detail: str
    action: str
    severity: str = "medium"  # low | medium | high
    affected: dict = field(default_factory=dict)


# Raw loading -----------------------------------------------------------------


def sim_number(path: Path) -> int:
    return int(re.search(r"(\d+)", path.stem).group(1))


def raw_files(raw_dir: Path = RAW_DIR) -> list[Path]:
    files = sorted(raw_dir.glob(SIM_GLOB), key=sim_number)
    if not files:
        raise FileNotFoundError(f"No simulation CSVs matching '{SIM_GLOB}' in {raw_dir}")
    return files


def _check_header(raw_header: list[str]) -> list[str]:
    """Return the positions whose raw header does not mention the expected bus/area."""
    canon = canonical_columns()
    if len(raw_header) != len(canon):
        raise ValueError(f"Expected {len(canon)} columns, found {len(raw_header)}")
    problems = []
    for raw, name in zip(raw_header[1:], canon[1:], strict=True):
        number = name.rsplit("_", 1)[1]
        digits = re.findall(r"\d+", raw)
        if number not in digits:
            problems.append(f"{raw.strip()!r} -> {name}")
    return problems


def read_raw(path: Path) -> tuple[pd.DataFrame, int]:
    """Read one CSV as text, map to canonical names and coerce to numbers.

    Returns the frame and the number of numeric cells that carried stray
    encoding characters (a UTF-8 non-breaking space read as cp1252 shows up as 'Â').
    """
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    bad = _check_header(list(df.columns))
    if bad:
        raise ValueError(f"{path.name}: header/position mismatch: {bad}")
    df.columns = canonical_columns()

    dirty = 0
    out = {"sim": np.full(len(df), sim_number(path))}
    for col in ["t", *NUMERIC_COLS]:
        s = df[col].str.strip()
        mask = s.str.contains("Â| ", regex=True)
        dirty += int(mask.sum())
        s = s.str.replace("Â", "", regex=False).str.replace(" ", "", regex=False).str.strip()
        out[col] = pd.to_numeric(s.replace("", np.nan), errors="coerce")
    for col in AREA_COLS:
        out[col] = (df[col].str.strip().str.upper() == "UNSTABLE").astype("int8")
    return pd.DataFrame(out), dirty


# Cleaning + audit ------------------------------------------------------------


def unstable_set(row: pd.Series) -> tuple[int, ...]:
    return tuple(a for a in AREAS if row[f"area_{a}"] == 1)


def build(raw_dir: Path = RAW_DIR) -> tuple[pd.DataFrame, dict]:
    """Load every simulation, repair what is safe to repair and audit the rest."""
    frames, dirty_cells = [], 0
    files = raw_files(raw_dir)
    for f in files:
        df, dirty = read_raw(f)
        frames.append(df)
        dirty_cells += dirty
    raw = pd.concat(frames, ignore_index=True)
    raw["t"] = raw["t"].round(2)
    df = raw.copy()
    issues: list[Issue] = []

    issues.append(
        Issue(
            "headers",
            "Inconsistent column headers",
            "Headers mix spacing and spelling ('BUS 26LOAD Q', 'BUS29LOADQ', 'ARA 4 CONDITION', "
            "'SHEDDING AT BUS 20P2'). All 56 files share the same layout, so columns are mapped by "
            "position, and every position is checked against the bus or area number in its header.",
            "Mapped to canonical names (v_25, lsf_25, shed_p_25, area_1, ...).",
            "low",
        )
    )
    issues.append(
        Issue(
            "encoding",
            "Stray encoding characters in numeric cells",
            f"{dirty_cells:,} cells carry a trailing 'Â' (a non-breaking space saved as UTF-8 and "
            "re-read as cp1252), which turns numbers into text.",
            "Stripped before numeric conversion.",
            "low",
            {"cells": dirty_cells},
        )
    )

    # Time grid
    expected = np.round(np.arange(0.02, 2.1001, 0.02), 2)
    present = np.sort(df.loc[df.sim == df.sim.min(), "t"].unique())
    missing = sorted(set(expected) - set(present))
    issues.append(
        Issue(
            "time_grid",
            "Gaps in the time grid",
            f"Each file has {len(present)} rows on a 0.02 s grid that should have {len(expected)}; "
            f"t = {', '.join(f'{m:.2f}' for m in missing)} s are absent in every file. All gaps fall "
            "before the fault, where the system is in steady state, so nothing is lost.",
            "Left as recorded.",
            "low",
            {"missing_t": [float(m) for m in missing]},
        )
    )

    # Pre-fault drift from the stable base case
    pre = df["t"] <= PRE_FAULT_END
    baseline = df.loc[(df.sim == 1) & (df.t == df.t.min()), NUMERIC_COLS].iloc[0]
    drift: dict[str, list[int]] = {}
    for col in NUMERIC_COLS:
        off = pre & ~np.isclose(df[col], baseline[col], equal_nan=True)
        if off.any():
            drift[col] = sorted(int(s) for s in df.loc[off, "sim"].unique())
            df.loc[off, col] = baseline[col]
    if "lsf_28" in drift:
        issues.append(
            Issue(
                "fill_series",
                "Spreadsheet fill-series artefact in BUS 28 LSF",
                "Before the fault every quantity should sit at its steady-state value, but BUS 28 LSF "
                "counts upward 0.00005, 1.00005, 2.00005, ... row by row: the signature of an Excel "
                "drag that incremented instead of copying. It also makes every pre-fault row unique, "
                "which hides how little information the pre-fault period carries.",
                "Reset to the base-case value 0.00005 for all pre-fault rows.",
                "high",
                {"sims": drift.pop("lsf_28")},
            )
        )
    for col, sims in drift.items():
        issues.append(
            Issue(
                f"drift_{col}",
                f"Pre-fault value out of place in {col}",
                f"{col} departs from its steady-state value before the fault in {len(sims)} "
                f"simulation(s) (for example {raw.loc[pre & (raw.sim == sims[0]), col].iloc[0]:g} "
                f"instead of {baseline[col]:g}). It looks like a value pasted into the wrong column.",
                "Reset to the base-case value for pre-fault rows.",
                "medium",
                {"sims": sims},
            )
        )

    # Post-fault gaps
    post = df["t"] > PRE_FAULT_END
    gaps = {c: int(df.loc[post, c].isna().sum()) for c in NUMERIC_COLS if df.loc[post, c].isna().any()}
    if gaps:
        issues.append(
            Issue(
                "post_gaps",
                "Empty cells after the fault",
                "A handful of post-fault cells are blank: " + ", ".join(f"{c} ({n})" for c, n in gaps.items()) + ".",
                "Left missing; models fill with 0 (no shedding) and the physics check skips them.",
                "low",
                gaps,
            )
        )

    # Base loads vs the IEEE 39-bus reference
    mism = {b: float(baseline[f"p_{b}"]) for b in LOAD_BUSES if not np.isclose(baseline[f"p_{b}"], IEEE39_LOAD_MW[b])}
    issues.append(
        Issue(
            "base_loads",
            "Base-case loads match the IEEE 39-bus reference",
            "All 19 monitored base-case loads equal the standard New England case (MATPOWER case39)"
            if not mism
            else f"Base loads differ from the IEEE reference at buses {sorted(mism)}.",
            "Validation check; no change.",
            "low" if not mism else "high",
            {"mismatched": mism},
        )
    )

    # Physically impossible post-fault values
    lsf_bad = {b: int((df.loc[post, f"lsf_{b}"] > 1).sum()) for b in LOAD_BUSES}
    lsf_bad = {b: n for b, n in lsf_bad.items() if n}
    if lsf_bad:
        issues.append(
            Issue(
                "lsf_range",
                "Load-shedding factors above 1",
                "A shedding factor is the fraction of a bus's load to drop, so it must lie between 0 and 1. "
                + "; ".join(
                    f"Bus {b} has {n} post-fault reading(s) above 1, up to {df.loc[post, f'lsf_{b}'].max():.2f}"
                    for b, n in lsf_bad.items()
                )
                + ". The shed MW was then computed from these factors, so the error carries through to the "
                "shedding totals. A slipped decimal point (9.82 for 0.982) is the likely cause.",
                "Flagged; excluded from the rule check, kept in the data.",
                "high",
                {str(b): n for b, n in lsf_bad.items()},
            )
        )
    over = {}
    for b in LOAD_BUSES:
        rows = df.loc[post & (df[f"shed_p_{b}"] > baseline[f"p_{b}"] + 1e-6)]
        if len(rows):
            follows_lsf = np.isclose(rows[f"shed_p_{b}"], rows[f"lsf_{b}"] * baseline[f"p_{b}"], rtol=0.05).mean()
            over[b] = (len(rows), float(rows[f"shed_p_{b}"].max()), float(follows_lsf))
    if over:
        parts = []
        for b, (n, mx, follows) in over.items():
            cause = (
                "a consequence of the factors above 1"
                if follows > 0.5
                else "and the values do not follow the bus's own factor, so the column was probably computed "
                "from another bus's load"
            )
            parts.append(
                f"Bus {b} sheds up to {mx:.1f} MW against a {baseline[f'p_{b}']:g} MW load ({n} readings), {cause}"
            )
        issues.append(
            Issue(
                "shed_exceeds_load",
                "Shedding larger than the load itself",
                "A bus cannot shed more than it consumes. " + "; ".join(parts) + ".",
                "Flagged; excluded from the rule check and from shedding totals in the app, kept in the data.",
                "high",
                {str(b): n for b, (n, _, _) in over.items()},
            )
        )

    # Label onset and scenario design
    per_sim = df[df.t > PRE_FAULT_END].groupby("sim")[AREA_COLS].max()
    recorded = {int(s): unstable_set(r) for s, r in per_sim.iterrows()}
    onset = df[df[AREA_COLS].sum(axis=1) > 0].groupby("sim")["t"].min()
    early = sorted(int(s) for s, t in onset.items() if t < 2.0)
    issues.append(
        Issue(
            "label_onset",
            "Labels switch on before the fault",
            f"In {len(early)} simulations the area labels read UNSTABLE from t = 1.98 s, one step "
            "before any voltage moves. The labels describe the scenario, not a measured outcome, so "
            "pre-fault rows labelled UNSTABLE carry no signal for a model.",
            "Models use post-fault rows only (t >= 2.00 s).",
            "medium",
            {"sims": early},
        )
    )
    mismatches = {
        s: {"recorded": list(recorded[s]), "design": list(DESIGN[s])} for s in recorded if recorded[s] != DESIGN[s]
    }
    issues.append(
        Issue(
            "design_labels",
            "Labels that break the scenario pattern",
            "Simulations follow a strict enumeration (base case, each single area, then every pair of "
            "areas). "
            + "; ".join(
                f"Sim {s} is labelled {tuple(v['recorded']) or 'stable'} where the pattern implies {tuple(v['design'])}"
                for s, v in mismatches.items()
            )
            + ". These need confirming with the engineer who ran the simulations.",
            "Kept as recorded; models are also evaluated with these simulations excluded.",
            "high",
            {str(s): v for s, v in mismatches.items()},
        )
    )

    # Duplicate scenarios
    def signature(frame: pd.DataFrame, cols: list[str]) -> dict[int, bytes]:
        return {int(s): g[cols].round(6).to_numpy().tobytes() for s, g in frame.groupby("sim")}

    full = signature(raw, ["t", *NUMERIC_COLS, *AREA_COLS])
    duplicates: dict[int, int] = {}
    for s in sorted(full):
        first = next(o for o in sorted(full) if full[o] == full[s])
        if first != s:
            duplicates[s] = first
    if duplicates:
        missing_design = [DESIGN[s] for s in duplicates]
        issues.append(
            Issue(
                "duplicate_files",
                "A simulation file is an exact copy of another",
                "; ".join(
                    f"Power System {s}.csv is byte-for-byte identical to Power System {o}.csv"
                    for s, o in duplicates.items()
                )
                + ". By the scenario pattern the copy should have held "
                + ", ".join(f"Area {' + '.join(map(str, d))}" for d in missing_design)
                + " unstable, so that scenario is missing from the study. Left in, the copy also leaks: a model "
                "tested on one twin has trained on the other.",
                "Copy dropped from modelling; the missing scenario is a question for the engineer.",
                "high",
                {str(s): o for s, o in duplicates.items()},
            )
        )
    volts = signature(df[post], V_COLS)
    shared = sorted(
        {
            s
            for s in volts
            for o in volts
            if s != o
            and volts[s] == volts[o]
            and recorded[s] != recorded[o]
            and s not in duplicates
            and o not in duplicates
        }
    )
    if shared:
        issues.append(
            Issue(
                "shared_voltages",
                "Different scenarios with identical voltage responses",
                "Sims "
                + " and ".join(map(str, shared))
                + " are labelled with different unstable areas ("
                + " vs ".join(f"{recorded[s]}" for s in shared)
                + ") yet every post-fault bus voltage is identical; only a few shedding columns differ. One file "
                "probably received the other's voltage block. No model can tell them apart, so at least one "
                "label is unreachable.",
                "Kept; both flagged as suspect and excluded from the clean evaluation.",
                "high",
                {"sims": shared},
            )
        )

    # Duplicate rows (effective sample size)
    distinct_post = df[post].groupby("sim")[V_COLS].apply(lambda g: len(g.drop_duplicates()))
    issues.append(
        Issue(
            "sample_size",
            "56 scenarios, not 5,700 samples",
            f"{len(df):,} rows, but before the fault every row is a copy of the steady state, and after "
            f"it each scenario has only {int(distinct_post.median())} distinct snapshots (2.00 s to "
            "2.10 s). Splitting rows at random lets a model see near-copies of its test rows.",
            "All evaluation holds out whole scenarios (leave-one-scenario-out).",
            "high",
            {"rows": len(df), "scenarios": int(df.sim.nunique())},
        )
    )

    df = df.sort_values(["sim", "t"]).reset_index(drop=True)
    df["recorded_set"] = df["sim"].map(lambda s: ",".join(map(str, recorded[s])))
    df["design_set"] = df["sim"].map(lambda s: ",".join(map(str, DESIGN[s])))
    suspect = sorted({int(s) for s in mismatches} | set(shared))
    df["label_suspect"] = df["sim"].isin(suspect).astype("int8")
    df["duplicate_of"] = df["sim"].map(duplicates).fillna(0).astype("int16")

    audit = {
        "files": len(files),
        "rows": len(df),
        "scenarios": int(df.sim.nunique()),
        "issues": [asdict(i) for i in issues],
        "suspect_sims": suspect,
        "duplicate_sims": sorted(duplicates),
    }
    return df, audit


# Accessors for the app -------------------------------------------------------


def post_fault(df: pd.DataFrame) -> pd.DataFrame:
    """Rows from the fault onwards (t >= 2.00 s)."""
    return df[df["t"] >= 2.0 - 1e-9]


def scenario_labels(df: pd.DataFrame) -> pd.DataFrame:
    """One row per simulation with the recorded unstable-area indicators."""
    return post_fault(df).groupby("sim")[AREA_COLS].max()


def save_audit(audit: dict, path: Path) -> None:
    path.write_text(json.dumps(audit, indent=2))
