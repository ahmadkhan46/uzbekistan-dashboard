"""
trends.py — Compact sparkline area charts for the indicator trends grid.

Why a separate module?  The six trend charts share a single rendering pattern
(filled area, transparent background, value annotation) but are structurally
distinct from the three hero visualisations.  Isolating them here keeps
spiral.py, radar.py, and choropleth.py focused on their own chart logic.

Each chart is intentionally minimal — no title, no legend, just the data shape
and a latest-value stamp.  The surrounding HTML card supplies the label so
Plotly's margins stay small and the plot area fills the compact card height.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

BG_PAPER   = "rgba(0,0,0,0)"
BG_PLOT    = "rgba(0,0,0,0)"
TEXT_COLOR = "#e8eaf6"
MUTED      = "#8892b0"


def _fmt(value: float, unit: str) -> str:
    """
    Format a raw numeric value to a compact human-readable string.

    Unit-aware so GDP figures abbreviate to $B/$M while percentages and
    mortality rates keep two decimal places — prevents a single format rule
    from looking wrong across radically different indicator scales.
    """
    if unit == "US$":
        if value >= 1_000_000_000: return f"${value / 1e9:.1f}B"
        if value >= 1_000_000:     return f"${value / 1e6:.1f}M"
        return f"${value:,.0f}"
    if unit == "%":     return f"{value:.1f}%"
    if unit == "years": return f"{value:.1f} yrs"
    if unit == "/1k":   return f"{value:.1f}/1k"
    if unit == "t":     return f"{value:.2f} t"
    return f"{value:,.3g}"


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert '#rrggbb' hex to an rgba() string for Plotly fill colours."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def build_trend_chart(
    df: pd.DataFrame,
    code: str,
    label: str,
    unit: str,
    color: str,
    year_range: tuple[int, int],
) -> go.Figure:
    """
    Build a compact filled-area sparkline for one WDI indicator.

    The chart is designed to sit inside a 155 px tall card.  It omits a chart
    title (the surrounding HTML supplies the label) and uses a minimal margin
    so the plot area maximises the available height.  The latest value is
    stamped as a Plotly annotation in the indicator's accent colour, mirroring
    the professor's sample layout.

    Parameters
    ----------
    df         : Uzbekistan long-format DataFrame (from data_loader.load_uzbekistan)
    code       : WDI Series Code to plot
    label      : Human-readable indicator name (used in hover tooltip only)
    unit       : Unit string for value formatting — '%', 'US$', 'years', '/1k', 't'
    color      : CSS hex colour for the line, fill, and value annotation
    year_range : (start_year, end_year) tuple driven by the year dropdowns

    Returns
    -------
    go.Figure  transparent-background area chart, ~155 px display height
    """
    from dashboard.data_loader import get_series

    series = get_series(df, code)
    series = series[
        (series["Year"] >= year_range[0]) & (series["Year"] <= year_range[1])
    ]

    if series.empty:
        return _empty_chart(label)

    years  = series["Year"].values.astype(int)
    values = series["Value"].values.astype(float)
    y_min  = float(np.nanmin(values))
    y_max  = float(np.nanmax(values))

    fig = go.Figure()

    # Filled area anchors to zero so negative GDP growth years dip below the
    # baseline rather than appearing as missing data.
    fig.add_trace(go.Scatter(
        x         = years,
        y         = values,
        mode      = "lines",
        line      = dict(color=color, width=2, shape="spline", smoothing=0.6),
        fill      = "tozeroy",
        fillcolor = _rgba(color, 0.14),
        hovertemplate = (
            "<b>%{x}</b><br>"
            f"{label}: <b>%{{y:,.3g}} {unit}</b><extra></extra>"
        ),
    ))

    # Latest-value stamp — mirrors the professor's sample where the current
    # reading appears in accent colour at the top-right of the chart area.
    fig.add_annotation(
        text      = f"<b>{_fmt(float(values[-1]), unit)}</b>",
        x=1, y=1, xref="paper", yref="paper",
        xanchor   = "right", yanchor = "top",
        showarrow = False,
        font      = dict(color=color, size=15, family="Inter"),
    )

    fig.update_layout(
        paper_bgcolor = BG_PAPER,
        plot_bgcolor  = BG_PLOT,
        margin        = dict(l=48, r=10, t=8, b=32),
        xaxis = dict(
            showgrid       = False,
            zeroline       = False,
            tickmode       = "array",
            tickvals       = [int(years[0]), int(years[-1])],
            ticktext       = [str(years[0]),  str(years[-1])],
            tickfont       = dict(color=MUTED, size=11),
        ),
        yaxis = dict(
            showgrid      = True,
            gridcolor     = "rgba(255,255,255,0.05)",
            zeroline      = True,
            zerolinecolor = "rgba(255,255,255,0.12)",
            zerolinewidth = 1,
            tickmode      = "array",
            tickvals      = [y_min, y_max],
            ticktext      = [f"{y_min:.1f}", f"{y_max:.1f}"],
            tickfont      = dict(color=MUTED, size=11),
        ),
        showlegend = False,
        hoverlabel = dict(bgcolor="#1a1d2e", font_color=TEXT_COLOR, font_size=13),
    )
    return fig


def _empty_chart(label: str) -> go.Figure:
    """Transparent placeholder shown when no data exists for the selected range."""
    fig = go.Figure()
    fig.add_annotation(
        text=f"No data · {label}", x=0.5, y=0.5,
        xref="paper", yref="paper", showarrow=False,
        font=dict(color=MUTED, size=10),
    )
    fig.update_layout(
        paper_bgcolor=BG_PAPER, plot_bgcolor=BG_PLOT,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        margin=dict(l=4, r=4, t=4, b=4),
    )
    return fig
