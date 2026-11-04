"""Build the cleaned simulation table and the data-quality audit.

    python scripts/build_dataset.py

Reads data/raw/Power System *.csv and writes
data/processed/simulations.parquet and data/processed/audit.json.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import AUDIT_PATH, LONG_PATH, PROCESSED_DIR  # noqa: E402
from src.data import build, save_audit  # noqa: E402
from src.physics import rule_scores  # noqa: E402


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df, audit = build()
    audit["physics"] = rule_scores(df)
    df.to_parquet(LONG_PATH, index=False)
    save_audit(audit, AUDIT_PATH)

    print(f"{audit['files']} files, {audit['rows']:,} rows -> {LONG_PATH.relative_to(PROCESSED_DIR.parents[1])}")
    for issue in audit["issues"]:
        print(f"  [{issue['severity']:>6}] {issue['title']}")
    phys = audit["physics"]
    print(f"Rule check: shed = LSF x load  R2 = {phys['r2_lsf_x_load']:.4f}")
    print(
        f"            shed = 0.8 dV x load R2 = {phys['r2_from_voltage']:.4f}  (median gain {phys['median_gain']:.3f})"
    )


if __name__ == "__main__":
    main()
