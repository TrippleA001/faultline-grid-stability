"""Project-wide configuration: paths, IEEE 39-bus metadata and scenario design."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = PROJECT_ROOT / "models"

BASE_CASE_XLSX = RAW_DIR / "psse_base_case.xlsx"
SIM_GLOB = "Power System *.csv"

LONG_PATH = PROCESSED_DIR / "simulations.parquet"
AUDIT_PATH = PROCESSED_DIR / "audit.json"
METRICS_PATH = MODEL_DIR / "metrics.json"
PREDICTIONS_PATH = MODEL_DIR / "loso_predictions.parquet"
MODEL_PATH = MODEL_DIR / "area_classifier.joblib"

# ---------------------------------------------------------------------------
# Simulation layout
# ---------------------------------------------------------------------------
# The 19 monitored load buses, in the column order the PSS/E export uses.
LOAD_BUSES = [25, 26, 28, 29, 27, 18, 24, 3, 39, 4, 16, 15, 21, 20, 23, 31, 12, 7, 8]
N_AREAS = 10
AREAS = list(range(1, N_AREAS + 1))

# The fault is applied at t = 2.00 s. The 1.98 s row is the last pre-fault sample
# (voltages unchanged) even though the area labels already read UNSTABLE there.
FAULT_TIME = 2.0
PRE_FAULT_END = 1.98

# The engineer's shedding rule, recovered from the data:
#   LSF        ~= LSF_GAIN * voltage deviation
#   shed P (Q)  = LSF * base-case load P (Q)
LSF_GAIN = 0.8

# ---------------------------------------------------------------------------
# IEEE 39-bus (New England) reference data
# ---------------------------------------------------------------------------
# Base-case loads from the standard case (MATPOWER case39). Used to validate the
# PSS/E export: every monitored bus matches exactly.
IEEE39_LOAD_MW = {
    3: 322.0, 4: 500.0, 7: 233.8, 8: 522.0, 12: 7.5, 15: 320.0, 16: 329.0, 18: 158.0,
    20: 628.0, 21: 274.0, 23: 247.5, 24: 308.6, 25: 224.0, 26: 139.0, 27: 281.0,
    28: 206.0, 29: 283.5, 31: 9.2, 39: 1104.0,
}  # fmt: skip

IEEE39_BRANCHES = [
    (1, 2), (1, 39), (2, 3), (2, 25), (2, 30), (3, 4), (3, 18), (4, 5), (4, 14), (5, 6),
    (5, 8), (6, 7), (6, 11), (6, 31), (7, 8), (8, 9), (9, 39), (10, 11), (10, 13), (10, 32),
    (12, 11), (12, 13), (13, 14), (14, 15), (15, 16), (16, 17), (16, 19), (16, 21), (16, 24),
    (17, 18), (17, 27), (19, 20), (19, 33), (20, 34), (21, 22), (22, 23), (22, 35), (23, 24),
    (23, 36), (25, 26), (25, 37), (26, 27), (26, 28), (26, 29), (28, 29), (29, 38),
]  # fmt: skip

GENERATOR_BUSES = list(range(30, 40))

# Schematic one-line layout (not geographic), loosely following the textbook
# New England diagram. Coordinates are arbitrary units on a 10 x 10 canvas.
BUS_XY = {
    1: (0.6, 6.0), 2: (2.0, 8.0), 3: (2.6, 6.6), 4: (2.6, 5.0), 5: (2.0, 3.8),
    6: (2.6, 2.6), 7: (1.5, 2.3), 8: (1.4, 1.2), 9: (0.3, 1.0), 10: (4.5, 2.0),
    11: (3.5, 2.6), 12: (4.1, 3.3), 13: (5.0, 3.3), 14: (4.0, 4.5), 15: (5.2, 4.6),
    16: (6.5, 5.1), 17: (5.5, 5.9), 18: (4.0, 6.6), 19: (6.5, 3.1), 20: (6.2, 1.8),
    21: (7.6, 6.1), 22: (9.0, 6.1), 23: (9.0, 4.3), 24: (7.8, 4.7), 25: (3.6, 8.6),
    26: (5.6, 8.6), 27: (5.6, 7.2), 28: (7.6, 8.6), 29: (9.1, 8.6), 30: (2.0, 9.6),
    31: (2.6, 1.0), 32: (4.5, 0.6), 33: (7.6, 2.5), 34: (6.2, 0.5), 35: (9.8, 7.0),
    36: (9.8, 3.4), 37: (3.6, 9.8), 38: (9.1, 9.8), 39: (0.4, 4.3),
}  # fmt: skip

# ---------------------------------------------------------------------------
# Scenario design
# ---------------------------------------------------------------------------


def design_scenarios() -> dict[int, tuple[int, ...]]:
    """Unstable-area set implied by the systematic scenario enumeration.

    Simulation 1 is the stable base case, 2-11 make one area unstable at a time,
    and 12-56 walk through every pair of areas in order of increasing gap
    ((1,2), (2,3), ..., (9,10), then (1,3), (2,4), ..., finally (1,10)).
    """
    design: dict[int, tuple[int, ...]] = {1: ()}
    sim = 2
    for area in AREAS:
        design[sim] = (area,)
        sim += 1
    for gap in range(1, N_AREAS):
        for first in range(1, N_AREAS - gap + 1):
            design[sim] = (first, first + gap)
            sim += 1
    return design


DESIGN = design_scenarios()
