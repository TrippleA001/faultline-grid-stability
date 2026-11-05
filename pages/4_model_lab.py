"""Model Lab: honest evaluation of unstable-area classification."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from src.charts import accuracy_trap_bars, leaderboard, per_area_f1, scenario_matrix, window_curve
from src.store import load_metrics, load_predictions
from src.theme import ACCENT, STABLE, UNSTABLE, footer, kpi, note, page_header, section

metrics = load_metrics()
preds = load_predictions()
trap = metrics["accuracy_trap"]
best_name = metrics["best"]
best = metrics["models"][best_name]

page_header(
    "PAGE 03 · MODEL LAB",
    "What the data can actually support",
    "Every number on this page comes from a model that never saw any row of the scenario it is scored on. "
    f"With {metrics['n_scenarios']} distinct scenarios that is the only protocol that measures generalisation to a new fault.",
)

section("01", "The accuracy trap", "Same data, same kind of model, three ways of splitting it.")
a, b = st.columns([3, 2])
with a, st.container(border=True):
    st.plotly_chart(accuracy_trap_bars(trap), width="stretch")
with b:
    st.markdown("#### Why accuracy lies here")
    st.markdown(
        f"- **{trap['share_stable_rows']:.0%}** of the {trap['rows']:,} rows are labelled stable, mostly "
        "identical pre-fault copies, so always answering *stable* is right that often.\n"
        "- A random row split puts near-identical post-fault snapshots of the same scenario on both sides, "
        "so the model can memorise a scenario instead of learning a pattern.\n"
        "- Holding out whole scenarios keeps accuracy high (stable rows are easy) but exposes how weak "
        "recognition of *which* area failed really is."
    )
    note(
        "Original notebook figures are its own reported test results: accuracy 93.3%, macro-F1 0.12, regressor R² 0.54."
    )

section(
    "02",
    "Which areas are unstable?",
    "Multi-label task: 10 yes/no answers per scenario, from post-fault voltage deviations.",
)
k1, k2, k3, k4 = st.columns(4)
s = best["all"]
with k1:
    kpi("Micro-F1", f"{s['micro_f1']:.2f}", f"{best_name.lower()}", ACCENT)
with k2:
    kpi("Macro-F1", f"{s['macro_f1']:.2f}", "averaged over the 10 areas")
with k3:
    kpi("Exact set right", f"{s['exact_match']:.0%}", "all 10 areas correct", UNSTABLE)
with k4:
    kpi(
        "Area-level accuracy",
        f"{s['area_accuracy']:.0%}",
        f"base rate unstable {metrics['label_base_rate']:.0%}",
        STABLE,
    )

view = st.radio(
    "Scenarios scored",
    [f"All {metrics['n_scenarios']}", f"Excluding {len(metrics['suspect_sims'])} suspect scenarios"],
    horizontal=True,
)
key = "all" if view.startswith("All") else "without_suspect"
a, b = st.columns(2)
with a, st.container(border=True):
    st.markdown("**Leaderboard**")
    st.plotly_chart(leaderboard(metrics["models"], key=key), width="stretch")
with b, st.container(border=True):
    st.markdown(f"**Per-area F1**, {best_name.lower()}")
    st.plotly_chart(per_area_f1(best[key]), width="stretch")

note(
    "The simplest model wins. With one example of each single-area fault and one of each pair, flexible models "
    "like random forests have too little to work with; a regularised linear model generalises better."
)

section("03", "How soon after the fault can it tell?", "Score as more post-fault snapshots (20 ms apart) are added.")
a, b = st.columns([3, 2])
with a, st.container(border=True):
    st.plotly_chart(window_curve(metrics["windows"]), width="stretch")
with b:
    first, last = metrics["windows"][0], metrics["windows"][-1]
    st.markdown("#### Early warning")
    st.markdown(
        f"The snapshot at the fault instant alone gives micro-F1 **{first['micro_f1']:.2f}**; adding the next "
        f"{last['ms_after_fault']} ms leaves it at **{last['micro_f1']:.2f}**. Almost all the usable signal is in "
        "the first post-fault voltage profile, which is good news for fast protection. Later snapshots add swing, "
        "not new information."
    )

section(
    "04",
    "Every scenario, out of sample",
    "Colour is the model's P(unstable); red rings mark what the study recorded; ⚑ marks suspect labels.",
)
with st.container(border=True):
    st.plotly_chart(scenario_matrix(preds, metrics["suspect_sims"], height=900), width="stretch")

section("05", "Limits, stated plainly")
st.markdown(
    f"- **{metrics['n_scenarios']} distinct scenarios is the ceiling.** One file is a copy of another, and each pair "
    "of areas appears once, so no model sees a repeat of the fault it is tested on. More simulations, not a bigger "
    "network, is the fix (the planned Tier 2 regenerates the case in the open-source ANDES simulator).\n"
    "- **Labels describe the scenario design.** They switch to UNSTABLE before voltages move, so they say which "
    "areas were stressed, not a measured stability margin.\n"
    f"- **{len(metrics['suspect_sims'])} scenarios have doubtful labels or inputs** (sims "
    + ", ".join(map(str, metrics["suspect_sims"]))
    + "). Scores are shown with and without them.\n"
    "- **The area-to-bus map is not in the export.** The model learns it implicitly; confirming it with the "
    "engineer would allow physically grounded features."
)
footer()
