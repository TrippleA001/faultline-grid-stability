"""Grid Explorer: step through any scenario on the one-line diagram."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from src.charts import area_strip, grid_diagram, shed_bars, voltage_traces
from src.config import AREAS, LOAD_BUSES
from src.physics import plausible_shed
from src.store import load_predictions, load_simulations, scenario_name
from src.theme import footer, kpi, note, page_header, section

df = load_simulations()
preds = load_predictions()
sims = sorted(df.sim.unique())
recorded = df.groupby("sim").recorded_set.first()
suspect = set(df.loc[df.label_suspect == 1, "sim"].unique())

page_header(
    "PAGE 01 · GRID EXPLORER",
    "Step through a fault",
    "Pick a scenario and a moment after the fault. The diagram shows how far each load bus has sagged, "
    "the strip shows which areas the study recorded as unstable, and the model's out-of-scenario guess.",
)

c1, c2 = st.columns([2, 3])
with c1:
    sim = st.selectbox(
        "Scenario",
        sims,
        index=sims.index(13) if 13 in sims else 0,
        format_func=lambda s: scenario_name(s, recorded[s]) + ("  ⚑" if s in suspect else ""),
    )
sim_df = df[df.sim == sim]
times = [t for t in sorted(sim_df.t.unique()) if t >= 2.0 - 1e-9]
with c2:
    t = st.select_slider(
        "Time after fault", options=times, value=times[1], format_func=lambda v: f"{(v - 2.0) * 1000:.0f} ms"
    )

row = sim_df[sim_df.t == t].iloc[0]
total_shed = float(plausible_shed(sim_df[sim_df.t == t]).sum(axis=1).iloc[0])
worst_bus = max(LOAD_BUSES, key=lambda b: row[f"v_{b}"] if row[f"v_{b}"] == row[f"v_{b}"] else -1)

if sim in suspect:
    note(
        f"<b>Label flagged.</b> Sim {sim} is recorded as Area {recorded[sim] or 'none'} but the scenario pattern "
        f"implies Area {row.design_set.replace(',', ' + ')}. See the Data Audit page."
    )

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi("Unstable areas (recorded)", recorded[sim].replace(",", " + ") or "none", "from the PSS/E study", compact=True)
with k2:
    kpi("Deepest sag", f"Bus {worst_bus}", f"dV = <b>{row[f'v_{worst_bus}']:.2f}</b> p.u.", compact=True)
with k3:
    kpi("Load shed at this step", f"{total_shed:,.0f} <small>MW</small>", "19 buses, impossible readings excluded")
p = preds[preds.sim == sim].sort_values("area")
with k4:
    if len(p):
        hits = int(((p.p_unstable >= 0.5) == (p.truth == 1)).sum())
        kpi("Model agreement", f"{hits}/10", "areas, model never saw this scenario")
    else:
        kpi("Model agreement", "n/a", f"duplicate of Sim {int(row.duplicate_of)}, not modelled", compact=True)

left, right = st.columns([3, 2])
with left, st.container(border=True):
    st.plotly_chart(grid_diagram({b: row[f"v_{b}"] for b in LOAD_BUSES}, height=540), width="stretch")
with right:
    with st.container(border=True):
        st.markdown("**Area status**: tiles are recorded, the dotted line is the model's P(unstable)")
        st.plotly_chart(
            area_strip([int(row[f"area_{a}"]) for a in AREAS], p.p_unstable.tolist() if len(p) else None, height=190),
            width="stretch",
        )
    with st.container(border=True):
        st.markdown("**Voltage deviation at every load bus**")
        st.plotly_chart(voltage_traces(sim_df, height=300), width="stretch")

section(
    "02", "Where the load comes off", "Recorded shedding per bus at the selected step, against the engineer's rule."
)
with st.container(border=True):
    st.plotly_chart(shed_bars(row), width="stretch")
note(
    "Diamonds are LSF × base-case load computed from the recorded LSF. Where they sit on the bar, the study "
    "followed its own rule exactly. The Load Shedding page checks this across every scenario."
)
footer()
