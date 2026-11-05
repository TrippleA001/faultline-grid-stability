"""Data Audit: every issue found in the export, and the questions it raises."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from src.store import load_audit
from src.theme import ACCENT, MUTED, UNSTABLE, footer, kpi, note, page_header, section

audit = load_audit()
issues = audit["issues"]
SEV_COLOR = {"high": UNSTABLE, "medium": ACCENT, "low": MUTED}

page_header(
    "PAGE 04 · DATA AUDIT",
    "What the export told us, and what it hid",
    "Every check below runs automatically in scripts/build_dataset.py. Repairs are limited to cases where "
    "the correct value is certain; anything that needs engineering judgement is flagged, not changed.",
)

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi("Files", f"{audit['files']}", "PSS/E CSV exports")
with k2:
    kpi("Rows", f"{audit['rows']:,}", "0.02 s steps, 0.02 to 2.10 s")
with k3:
    kpi("High-severity findings", f"{sum(i['severity'] == 'high' for i in issues)}", "change the analysis", UNSTABLE)
with k4:
    kpi(
        "Labels to confirm",
        f"{len(audit['suspect_sims'])}",
        "sims " + ", ".join(map(str, audit["suspect_sims"])),
        ACCENT,
    )

section("01", "Findings", "Sorted by how much each one changes the conclusions.")
order = {"high": 0, "medium": 1, "low": 2}
for issue in sorted(issues, key=lambda i: order[i["severity"]]):
    color = SEV_COLOR[issue["severity"]]
    with st.container(border=True):
        st.markdown(
            f'<span class="mono small" style="color:{color}">● {issue["severity"].upper()}</span> '
            f"&nbsp;<b>{issue['title']}</b>",
            unsafe_allow_html=True,
        )
        st.markdown(issue["detail"])
        st.markdown(f'<span class="small muted">Action: {issue["action"]}</span>', unsafe_allow_html=True)

section("02", "Questions for the engineer", "The collaboration loop: data findings go back to the domain expert.")
design = next((i for i in issues if i["key"] == "design_labels"), None)
dupes = audit.get("duplicate_sims", [])
questions = []
if dupes:
    questions.append(
        "Power System "
        + ", ".join(map(str, dupes))
        + ".csv is an exact copy of another file. Can the intended run (Area 4 alone unstable, by the scenario "
        "pattern) be re-exported from PSS/E?"
    )
if design:
    questions.append(
        "Sims "
        + ", ".join(design["affected"].keys())
        + " carry labels that break the scenario enumeration. Were these runs intentionally different, or were the "
        "labels copied from a neighbouring file?"
    )
if any(i["key"] == "shared_voltages" for i in issues):
    questions.append(
        "Sims 47 and 51 have identical bus voltages but different unstable areas. Which file holds the right "
        "voltage block?"
    )
questions += [
    "Bus 26 has shedding factors up to 11 and bus 12 sheds up to 93 MW from a 7.5 MW load. Are these entry errors, "
    "and what should the values be?",
    "Which buses belong to each of the 10 areas? The base-case workbook groups generators into 3 coherent areas; "
    "the 10-area split used for the labels is not in the export.",
    "Is an area labelled UNSTABLE because it was faulted by design, or because a stability index (for example "
    "the COI-referred rotor-angle index) crossed a threshold?",
    "The LSF is about 0.8 × voltage deviation at most buses. Is 0.8 a fixed design gain?",
    "After the fault the LOAD P/Q columns drop to fractions (for example 0.16 at bus 25, base 224 MW). Are these "
    "per-unit remaining load, or a different quantity?",
]
for i, q in enumerate(questions, 1):
    st.markdown(f"**Q{i}.** {q}")
note(
    "Answers to these questions are the cheapest way to improve the model. Each one either fixes labels, or "
    "turns an implicit pattern into an explicit, physically meaningful feature."
)

section("03", "Pipeline")
st.markdown(
    "1. **Load**: read each CSV as text, map 125 columns by position, verify each against its header's bus "
    "number, strip encoding debris, convert to numbers.\n"
    "2. **Repair**: reset pre-fault values that depart from the stable base case (the fill-series artefact and "
    "misplaced values).\n"
    "3. **Validate**: base-case loads against the IEEE 39-bus reference; labels against the scenario design; the "
    "shedding rule against recorded shed MW.\n"
    "4. **Model**: scenario-level features from post-fault voltage deviations; leave-one-scenario-out evaluation."
)
st.code("python scripts/build_dataset.py\npython scripts/train_models.py\nstreamlit run app.py", language="bash")
footer()
