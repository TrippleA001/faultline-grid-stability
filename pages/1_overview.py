"""Overview: the project in one page."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from src.charts import grid_diagram
from src.config import LOAD_BUSES
from src.data import post_fault
from src.store import load_audit, load_metrics, load_simulations
from src.theme import ACCENT, STABLE, UNSTABLE, footer, hero, kpi, note, section

df = load_simulations()
audit = load_audit()
metrics = load_metrics()
best = metrics["models"][metrics["best"]]["all"]
trap = metrics["accuracy_trap"]
phys = audit["physics"]

hero(
    "IEEE 39-BUS · PSS/E · LOAD SHEDDING",
    "When the grid <span>buckles</span>, which areas fail and how much load must go?",
    "A rebuild of an MSc power-systems study. An electrical engineer simulated 56 fault scenarios on the "
    "New England 39-bus system in PSS/E; this project audits that data, writes the engineer's shedding "
    "rule down as code, and measures honestly what machine learning can and cannot add.",
    [
        f"<b>{audit['scenarios']}</b> fault scenarios",
        f"<b>{len(LOAD_BUSES)}</b> monitored load buses",
        "<b>10</b> grid areas",
        "PSS/E time-domain simulation",
    ],
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi(
        "Original headline",
        f"{trap['original_notebook']['accuracy']:.0%}",
        "accuracy, but <b>macro-F1 0.12</b>",
        UNSTABLE,
    )
with c2:
    kpi("Shedding rule fit", f"R² {phys['r2_lsf_x_load']:.3f}", "shed = LSF × base load", ACCENT)
with c3:
    kpi("Held-out scenarios", f"{best['micro_f1']:.2f}", "micro-F1, unstable areas", STABLE)
with c4:
    kpi("Data issues logged", f"{len(audit['issues'])}", f"<b>{len(audit['suspect_sims'])}</b> labels to confirm", None)

section("01", "The story", "Three findings, each one changing what the project should claim.")
a, b, c = st.columns(3)
with a, st.container(border=True):
    st.markdown("#### 93% accuracy was a mirage")
    st.markdown(
        f"The first ML pass split rows at random. {trap['share_stable_rows']:.0%} of rows are steady-state "
        "copies labelled *stable*, so a model that always says *stable* is right that often. It never caught an "
        "unstable area in the test set."
    )
with b, st.container(border=True):
    st.markdown("#### The targets were a formula")
    st.markdown(
        f"An LSTM was trained to predict 38 shedding values (R² 0.54). The engineer's method sizes them as "
        f"**LSF ≈ {phys['median_gain']:.2f} × voltage deviation** and **shed = LSF × base load**. Written as "
        f"code, the rule reproduces the data with R² {phys['r2_lsf_x_load']:.3f} once {phys['implausible_cells']} "
        "physically impossible cells are set aside."
    )
with c, st.container(border=True):
    st.markdown("#### The real question is narrower")
    st.markdown(
        f"Which areas went unstable, judged from the first post-fault voltages? Holding out each scenario in "
        f"turn, logistic regression reaches micro-F1 {best['micro_f1']:.2f} (always-stable: 0.00). Real "
        f"signal, small data: {metrics['n_scenarios']} distinct scenarios is the ceiling."
    )

section(
    "02",
    "The worst snapshot in the study",
    "Voltage deviation 20 ms after the fault, for the scenario with the deepest sag.",
)
post = post_fault(df)
snap = post[post.t.round(2) == 2.02]
worst = snap.assign(total=snap[[f"v_{b}" for b in LOAD_BUSES]].sum(axis=1)).sort_values("total").iloc[-1]
left, right = st.columns([3, 2])
with left, st.container(border=True):
    st.plotly_chart(grid_diagram({b: worst[f"v_{b}"] for b in LOAD_BUSES}, height=520), width="stretch")
with right:
    st.markdown(f"#### Sim {int(worst.sim)}: Area {worst.recorded_set.replace(',', ' + Area ')} unstable")
    st.markdown(
        "Each circle is a monitored load bus, sized by its base-case load and coloured by voltage deviation "
        "(0 = nominal, 1 = collapse). Squares are the ten generators. Grey dots are transmission buses that "
        "the study did not monitor."
    )
    note(
        "<b>Schematic layout.</b> Positions follow the textbook New England diagram, not geography. "
        "Branch list from the standard IEEE 39-bus case."
    )
    st.page_link("pages/2_grid_explorer.py", label="Open the Grid Explorer", icon=":material/arrow_forward:")

section("03", "Who did what", "A data-science rebuild that treats the engineer's simulations as ground truth.")
x, y = st.columns(2)
with x, st.container(border=True):
    st.markdown("#### Domain expert · electrical engineering MSc")
    st.markdown(
        "- Built the IEEE 39-bus case in **PSS/E** and ran 56 fault scenarios\n"
        "- Defined the 10-area split and the stability criterion\n"
        "- Designed the voltage-based load-shedding scheme, following "
        "[Abdul Wahab & Mohamed (2012)](https://doi.org/10.1155/2012/410461)"
    )
with y, st.container(border=True):
    st.markdown("#### Data science · AbdulSamad")
    st.markdown(
        "- Audited the export: encoding, a fill-series artefact, misplaced values, suspect labels\n"
        "- Recovered the shedding rule from data and validated loads against the IEEE reference\n"
        "- Replaced the leaky row split with leave-one-scenario-out evaluation\n"
        "- Built this app and the open questions list for the engineer"
    )

st.markdown(
    f'<p class="small muted" style="margin-top:1rem">Colour key: <span style="color:{STABLE}">stable</span> → '
    f'<span style="color:{UNSTABLE}">severe</span>.</p>',
    unsafe_allow_html=True,
)
footer()
