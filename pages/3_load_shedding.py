"""Load Shedding: the engineer's rule, recovered and checked."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.charts import _layout, lsf_vs_voltage, rule_scatter
from src.config import LOAD_BUSES, LSF_GAIN
from src.data import post_fault
from src.physics import total_shed
from src.store import load_audit, load_metrics, load_simulations
from src.theme import ACCENT, MUTED, footer, kpi, note, page_header, section

df = load_simulations()
audit = load_audit()
metrics = load_metrics()
phys = audit["physics"]
post = post_fault(df)
post = post[post.t > 2.0 - 1e-9]

page_header(
    "PAGE 02 · LOAD SHEDDING",
    "The rule behind the numbers",
    "The first ML pass trained an LSTM to predict 38 shedding values. Before learning anything, it is "
    "worth asking how the engineer computed them. The answer is two lines of arithmetic.",
)

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi(
        "LSTM regressor (original)",
        f"R² {metrics['accuracy_trap']['original_notebook']['regressor_r2']:.2f}",
        "38 shed P/Q targets",
    )
with k2:
    kpi(
        "Rule, recorded LSF",
        f"R² {phys['r2_lsf_x_load']:.3f}",
        f"excluding {phys['implausible_cells']} impossible cells",
        ACCENT,
    )
with k3:
    kpi("Rule, from voltage only", f"R² {phys['r2_from_voltage']:.2f}", f"LSF = {LSF_GAIN} × dV")
with k4:
    kpi("Fitted gain", f"{phys['median_gain']:.2f}", "median LSF / dV over 19 buses")

section(
    "01", "Step 2: shed = LSF × base-case load", "Every post-fault bus reading in the study, recorded against the rule."
)
a, b = st.columns(2)
with a, st.container(border=True):
    st.plotly_chart(rule_scatter(post), width="stretch")
with b:
    st.markdown("#### Why this matters for the ML")
    st.markdown(
        "The shed MW at each bus is the load-shedding factor times that bus's base-case load, which the "
        "study holds fixed. A neural network asked to predict shed MW is relearning a multiplication, and "
        "doing it worse than the formula. The useful split of work is:\n\n"
        "- **Physics** sizes the shedding once a bus's LSF is known.\n"
        "- **ML** is only worth trying where no formula exists: deciding *which areas* have lost stability."
    )
    note(
        "Points off the diagonal are the handful of cells where the export disagrees with its own rule, "
        "mostly the misplaced values listed on the Data Audit page."
    )

section(
    "02", "Step 1: LSF from voltage deviation", "The factor grows in proportion to how far the bus voltage has sagged."
)
a, b = st.columns(2)
with a, st.container(border=True):
    st.plotly_chart(lsf_vs_voltage(post), width="stretch")
with b, st.container(border=True):
    per_bus = pd.DataFrame(phys["per_bus"]).rename(
        columns={"bus": "Bus", "r2_lsf_x_load": "R² (LSF × load)", "r2_from_voltage": f"R² ({LSF_GAIN} dV × load)"}
    )
    per_bus["Gain"] = [phys["gains"][str(b)] for b in per_bus.Bus]
    st.dataframe(per_bus.round(3), hide_index=True, width="stretch", height=380)
note(
    f"A single gain of {LSF_GAIN} fits most buses closely. Buses 18 and 26 scatter more, which is a question "
    "for the engineer: a different setting, or rounding in the export?"
)

section("03", "How much load each scenario sheds", "Peak total active-power shedding after the fault.")
tot = total_shed(df).groupby("sim").shed_mw.max().reset_index()
labels = df.groupby("sim").recorded_set.first()
tot["label"] = tot.sim.map(lambda s: f"Sim {s} ({labels[s] or 'stable'})")
tot = tot.sort_values("shed_mw", ascending=False)
fig = go.Figure(
    go.Bar(
        x=tot.label,
        y=tot.shed_mw,
        marker_color=ACCENT,
        hovertemplate="%{x}<br>%{y:,.0f} MW<extra></extra>",
    )
)
fig.update_layout(**_layout(360))
fig.update_xaxes(showticklabels=False, title=dict(text="Scenarios, ranked", font=dict(color=MUTED)))
fig.update_yaxes(title=dict(text="Peak shed (MW)", font=dict(color=MUTED)))
with st.container(border=True):
    st.plotly_chart(fig, width="stretch")
st.caption(
    f"Total base-case load on the {len(LOAD_BUSES)} monitored buses: {sum(df.iloc[0][f'p_{b}'] for b in LOAD_BUSES):,.0f} MW."
)
footer()
