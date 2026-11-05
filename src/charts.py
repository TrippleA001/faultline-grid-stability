"""Plotly figures, styled to sit on the dark theme."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .config import AREAS, BUS_XY, GENERATOR_BUSES, IEEE39_BRANCHES, IEEE39_LOAD_MW, LOAD_BUSES, LSF_GAIN
from .theme import ACCENT, GRID_BLUE, INK, MUTED, STABLE, UNSTABLE

FONT = "Manrope, -apple-system, sans-serif"
GRIDLINE = "rgba(234, 240, 250, 0.07)"
SEVERITY = [[0.0, STABLE], [0.25, "#A3E635"], [0.5, ACCENT], [0.75, "#FB923C"], [1.0, UNSTABLE]]


def _layout(height: int = 360, **overrides) -> dict:
    base = dict(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=INK, size=12),
        xaxis=dict(gridcolor=GRIDLINE, zerolinecolor=GRIDLINE, linecolor=GRIDLINE, tickfont=dict(color=MUTED)),
        yaxis=dict(gridcolor=GRIDLINE, zerolinecolor=GRIDLINE, linecolor=GRIDLINE, tickfont=dict(color=MUTED)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED, size=11), orientation="h", y=1.08, x=0),
        hoverlabel=dict(bgcolor="#0B1220", bordercolor=ACCENT, font=dict(family=FONT, color=INK)),
    )
    base.update(overrides)
    return base


# Grid ------------------------------------------------------------------------


def grid_diagram(bus_value: dict[int, float], height: int = 560, value_label: str = "Voltage deviation") -> go.Figure:
    """Schematic IEEE 39-bus one-line diagram, load buses coloured by ``bus_value`` (0-1)."""
    fig = go.Figure()
    ex, ey = [], []
    for a, b in IEEE39_BRANCHES:
        (x0, y0), (x1, y1) = BUS_XY[a], BUS_XY[b]
        ex += [x0, x1, None]
        ey += [y0, y1, None]
    fig.add_trace(
        go.Scatter(x=ex, y=ey, mode="lines", line=dict(color="rgba(148,163,184,0.35)", width=1.6), hoverinfo="skip")
    )

    other = [b for b in BUS_XY if b not in LOAD_BUSES and b not in GENERATOR_BUSES]
    fig.add_trace(
        go.Scatter(
            x=[BUS_XY[b][0] for b in other],
            y=[BUS_XY[b][1] for b in other],
            mode="markers",
            marker=dict(size=7, color="#1E293B", line=dict(color="rgba(148,163,184,0.6)", width=1)),
            text=[f"Bus {b}<br>Transmission bus (not monitored)" for b in other],
            hovertemplate="%{text}<extra></extra>",
        )
    )
    gens = [b for b in GENERATOR_BUSES if b not in LOAD_BUSES]
    fig.add_trace(
        go.Scatter(
            x=[BUS_XY[b][0] for b in gens],
            y=[BUS_XY[b][1] for b in gens],
            mode="markers+text",
            marker=dict(symbol="square", size=15, color="#0B1220", line=dict(color=GRID_BLUE, width=2)),
            text=["G" for _ in gens],
            textfont=dict(color=GRID_BLUE, size=9),
            customdata=[[b] for b in gens],
            hovertemplate="Bus %{customdata[0]}<br>Generator<extra></extra>",
        )
    )

    vals = [float(np.nan_to_num(bus_value.get(b, 0.0))) for b in LOAD_BUSES]
    sizes = [12 + 16 * np.sqrt(IEEE39_LOAD_MW[b] / max(IEEE39_LOAD_MW.values())) for b in LOAD_BUSES]
    fig.add_trace(
        go.Scatter(
            x=[BUS_XY[b][0] for b in LOAD_BUSES],
            y=[BUS_XY[b][1] for b in LOAD_BUSES],
            mode="markers+text",
            marker=dict(
                size=sizes,
                color=vals,
                cmin=0,
                cmax=1,
                colorscale=SEVERITY,
                line=dict(color="#070B14", width=2),
                colorbar=dict(
                    title=dict(text=value_label, font=dict(color=MUTED, size=11)),
                    tickfont=dict(color=MUTED),
                    thickness=10,
                    len=0.6,
                    outlinewidth=0,
                ),
            ),
            text=[str(b) for b in LOAD_BUSES],
            textposition="top center",
            textfont=dict(color=INK, size=10),
            customdata=[[b, IEEE39_LOAD_MW[b], v] for b, v in zip(LOAD_BUSES, vals, strict=True)],
            hovertemplate="Bus %{customdata[0]}<br>Base load %{customdata[1]:.1f} MW<br>"
            + value_label
            + " %{customdata[2]:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        **_layout(height, margin=dict(l=0, r=0, t=10, b=0)),
        showlegend=False,
    )
    fig.update_xaxes(visible=False, range=[-0.3, 10.4])
    fig.update_yaxes(visible=False, range=[0.0, 10.3], scaleanchor="x", scaleratio=1)
    return fig


def area_strip(truth: list[int], proba: list[float] | None = None, height: int = 150) -> go.Figure:
    """Ten area tiles: recorded state, with the out-of-scenario model probability if given."""
    fig = go.Figure()
    colors = [UNSTABLE if t else STABLE for t in truth]
    fig.add_trace(
        go.Bar(
            x=[f"A{a}" for a in AREAS],
            y=[1] * len(AREAS),
            marker=dict(color=colors, opacity=0.22, line=dict(color=colors, width=1.5)),
            customdata=["UNSTABLE" if t else "stable" for t in truth],
            name="Recorded (red = unstable)",
            hovertemplate="%{x}: %{customdata}<extra>recorded</extra>",
        )
    )
    if proba is not None:
        fig.add_trace(
            go.Scatter(
                x=[f"A{a}" for a in AREAS],
                y=proba,
                mode="markers+lines",
                line=dict(color=ACCENT, width=1.5, dash="dot"),
                marker=dict(size=9, color=ACCENT),
                name="Model P(unstable)",
                hovertemplate="%{x}: %{y:.0%}<extra>model</extra>",
            )
        )
    fig.update_layout(**_layout(height, margin=dict(l=0, r=0, t=26, b=0), bargap=0.12))
    fig.update_yaxes(range=[0, 1.02], tickformat=".0%", showgrid=False)
    return fig


def voltage_traces(sim_df: pd.DataFrame, height: int = 380) -> go.Figure:
    fig = go.Figure()
    window = sim_df[sim_df.t >= 1.9]
    for b in LOAD_BUSES:
        fig.add_trace(
            go.Scatter(
                x=window.t,
                y=window[f"v_{b}"],
                mode="lines+markers",
                line=dict(width=1.4),
                marker=dict(size=4),
                name=f"Bus {b}",
                hovertemplate=f"Bus {b}<br>t = %{{x:.2f}} s<br>dV = %{{y:.3f}}<extra></extra>",
            )
        )
    fig.add_vline(x=2.0, line=dict(color=UNSTABLE, dash="dash", width=1))
    fig.add_annotation(
        x=2.0, y=1, yref="paper", text="fault", showarrow=False, font=dict(color=UNSTABLE, size=11), xanchor="left"
    )
    fig.update_layout(**_layout(height), showlegend=False)
    fig.update_xaxes(title=dict(text="Time (s)", font=dict(color=MUTED)))
    fig.update_yaxes(title=dict(text="Voltage deviation (p.u.)", font=dict(color=MUTED)))
    return fig


def shed_bars(row: pd.Series, height: int = 340) -> go.Figure:
    recorded = [float(np.nan_to_num(row[f"shed_p_{b}"])) for b in LOAD_BUSES]
    rule = [float(np.nan_to_num(row[f"lsf_{b}"])) * IEEE39_LOAD_MW[b] for b in LOAD_BUSES]
    order = np.argsort(recorded)[::-1]
    x = [f"Bus {LOAD_BUSES[i]}" for i in order]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=[recorded[i] for i in order], name="Recorded (PSS/E study)", marker_color=GRID_BLUE))
    fig.add_trace(
        go.Scatter(
            x=x,
            y=[rule[i] for i in order],
            mode="markers",
            name="Rule: LSF × base load",
            marker=dict(symbol="diamond", size=10, color=ACCENT, line=dict(color="#070B14", width=1)),
        )
    )
    fig.update_layout(**_layout(height))
    fig.update_yaxes(title=dict(text="Active power shed (MW)", font=dict(color=MUTED)))
    return fig


# Physics ---------------------------------------------------------------------


def rule_scatter(post: pd.DataFrame, height: int = 380) -> go.Figure:
    xs, ys, labels = [], [], []
    for b in LOAD_BUSES:
        xs.append((post[f"lsf_{b}"] * IEEE39_LOAD_MW[b]).to_numpy())
        ys.append(post[f"shed_p_{b}"].to_numpy())
        labels += [f"Bus {b}"] * len(post)
    x, y = np.concatenate(xs), np.concatenate(ys)
    top = float(np.nanmax([np.nanmax(x), np.nanmax(y)]))
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=[0, top], y=[0, top], mode="lines", line=dict(color=MUTED, dash="dash", width=1), hoverinfo="skip")
    )
    fig.add_trace(
        go.Scattergl(
            x=x,
            y=y,
            mode="markers",
            marker=dict(size=5, color=ACCENT, opacity=0.55),
            text=labels,
            hovertemplate="%{text}<br>rule %{x:.1f} MW<br>recorded %{y:.1f} MW<extra></extra>",
        )
    )
    fig.update_layout(**_layout(height), showlegend=False)
    fig.update_xaxes(title=dict(text="LSF × base-case load (MW)", font=dict(color=MUTED)))
    fig.update_yaxes(title=dict(text="Recorded shed P (MW)", font=dict(color=MUTED)))
    return fig


def lsf_vs_voltage(post: pd.DataFrame, height: int = 380) -> go.Figure:
    v = np.concatenate([post[f"v_{b}"].to_numpy() for b in LOAD_BUSES])
    lsf = np.concatenate([post[f"lsf_{b}"].to_numpy() for b in LOAD_BUSES])
    ok = (v > 0.01) & ~np.isnan(lsf) & (lsf < 1.5)
    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=v[ok], y=lsf[ok], mode="markers", marker=dict(size=5, color=GRID_BLUE, opacity=0.5), name="Recorded"
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[0, 1], y=[0, LSF_GAIN], mode="lines", line=dict(color=ACCENT, width=2), name=f"LSF = {LSF_GAIN} × dV"
        )
    )
    fig.update_layout(**_layout(height))
    fig.update_xaxes(title=dict(text="Voltage deviation dV (p.u.)", font=dict(color=MUTED)))
    fig.update_yaxes(title=dict(text="Load-shedding factor", font=dict(color=MUTED)))
    return fig


# Models ----------------------------------------------------------------------


def accuracy_trap_bars(trap: dict, height: int = 340) -> go.Figure:
    groups = [
        "Original notebook<br>(LSTM, row windows)",
        "Random row split<br>(random forest)",
        "Held-out scenarios<br>(random forest)",
    ]
    acc = [
        trap["original_notebook"]["accuracy"],
        trap["random_row_split"]["accuracy"],
        trap["scenario_split"]["accuracy"],
    ]
    f1 = [
        trap["original_notebook"]["macro_f1"],
        trap["random_row_split"]["macro_f1"],
        trap["scenario_split"]["macro_f1_unstable_rows"],
    ]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=groups, y=acc, name="Accuracy", marker_color=MUTED, text=[f"{a:.0%}" for a in acc], textposition="outside"
        )
    )
    fig.add_trace(
        go.Bar(
            x=groups,
            y=f1,
            name="Macro-F1 on unstable classes",
            marker_color=UNSTABLE,
            text=[f"{a:.2f}" for a in f1],
            textposition="outside",
        )
    )
    fig.update_layout(**_layout(height, barmode="group"))
    fig.update_yaxes(range=[0, 1.12], tickformat=".0%")
    return fig


def leaderboard(models: dict, key: str = "all", height: int = 320) -> go.Figure:
    names = list(models)
    fig = go.Figure()
    for metric, label, color in [
        ("micro_f1", "Micro-F1", ACCENT),
        ("macro_f1", "Macro-F1", GRID_BLUE),
        ("exact_match", "Exact set match", STABLE),
    ]:
        vals = [models[n][key][metric] for n in names]
        fig.add_trace(
            go.Bar(
                y=names,
                x=vals,
                name=label,
                orientation="h",
                marker_color=color,
                text=[f"{v:.2f}" for v in vals],
                textposition="outside",
            )
        )
    fig.update_layout(**_layout(height, barmode="group"))
    fig.update_xaxes(range=[0, 1.05])
    fig.update_yaxes(autorange="reversed")
    return fig


def window_curve(windows: list[dict], height: int = 320) -> go.Figure:
    ms = [w["ms_after_fault"] for w in windows]
    fig = go.Figure()
    for metric, label, color in [("micro_f1", "Micro-F1", ACCENT), ("macro_f1", "Macro-F1", GRID_BLUE)]:
        fig.add_trace(
            go.Scatter(
                x=ms, y=[w[metric] for w in windows], mode="lines+markers", name=label, line=dict(color=color, width=2)
            )
        )
    fig.update_layout(**_layout(height))
    fig.update_xaxes(title=dict(text="Observation window after the fault (ms)", font=dict(color=MUTED)))
    fig.update_yaxes(range=[0, 1], title=dict(text="Score", font=dict(color=MUTED)))
    return fig


def per_area_f1(scores: dict, height: int = 300) -> go.Figure:
    vals = scores["per_area_f1"]
    fig = go.Figure(
        go.Bar(
            x=[f"Area {a}" for a in AREAS],
            y=vals,
            marker_color=ACCENT,
            text=[f"{v:.2f}" for v in vals],
            textposition="outside",
        )
    )
    fig.update_layout(**_layout(height))
    fig.update_yaxes(range=[0, 1.1], title=dict(text="F1", font=dict(color=MUTED)))
    return fig


def scenario_matrix(preds: pd.DataFrame, suspect: list[int], height: int = 520) -> go.Figure:
    """Scenario x area grid: colour = out-of-scenario P(unstable), ring = recorded unstable."""
    wide = preds.pivot(index="sim", columns="area", values="p_unstable").sort_index()
    truth = preds[preds.truth == 1]
    fig = go.Figure(
        go.Heatmap(
            z=wide.to_numpy(),
            x=list(wide.columns),
            y=list(wide.index),
            colorscale=[[0, "#0B1220"], [0.5, "#7C5A16"], [1, ACCENT]],
            zmin=0,
            zmax=1,
            colorbar=dict(
                title=dict(text="P(unstable)", font=dict(color=MUTED, size=11)),
                tickfont=dict(color=MUTED),
                thickness=10,
            ),
            hovertemplate="Sim %{y} · Area %{x}<br>P(unstable) %{z:.0%}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=truth.area,
            y=truth.sim,
            mode="markers",
            marker=dict(symbol="circle-open", size=11, color=UNSTABLE, line=dict(width=2)),
            name="Recorded unstable",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[10.62] * len(suspect),
            y=suspect,
            mode="text",
            text=["⚑"] * len(suspect),
            textfont=dict(color=UNSTABLE, size=13),
            name="Suspect label",
            hoverinfo="skip",
        )
    )
    fig.update_layout(**_layout(height, margin=dict(l=10, r=10, t=30, b=10)))
    fig.update_yaxes(
        autorange="reversed",
        tickvals=list(wide.index),
        ticktext=[f"Sim {s}" for s in wide.index],
        tickfont=dict(size=9, color=MUTED),
        showgrid=False,
        zeroline=False,
    )
    fig.update_xaxes(
        tickvals=list(wide.columns),
        ticktext=[f"A{a}" for a in wide.columns],
        range=[0.5, 10.9],
        showgrid=False,
        zeroline=False,
        side="top",
    )
    return fig
