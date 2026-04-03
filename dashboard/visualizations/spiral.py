"""
spiral.py — GDP growth spiral chart for Uzbekistan (2006-2024)

Encodes time angularly: each revolution spans YEARS_PER_LOOP years, coiling
outward so earlier years occupy the inner loops.  The radius is modulated by
the growth rate — above-average years push the arc outward, below-average
years pull it inward — giving the shape itself analytical meaning.

Why GDP growth for the spiral?  It is the most cyclically legible indicator
in the dataset: consistent ~7-9% through 2016, a reform-driven slowdown in
2017, a COVID shock in 2020, then sharp recovery.  The spiral makes these
rhythmic patterns visible in a way a line chart cannot.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ── Visual constants tied to the dark dashboard theme ──────────────────────
BG_PAPER   = "rgba(0,0,0,0)"      # transparent so the card background shows
BG_PLOT    = "rgba(0,0,0,0)"
TEXT_COLOR = "#e8eaf6"
MUTED      = "#8892b0"
ACCENT     = "#4f8ef7"
HIGHLIGHT  = "#f39c12"

# ── Spiral geometry ────────────────────────────────────────────────────────
YEARS_PER_LOOP = 5    # 19 years ÷ 5 ≈ 4 loops — keeps the spiral dense but readable
BASE_RADIUS    = 2.0  # radius of the innermost arc (arbitrary units)
LOOP_SPACING   = 1.8  # radial gap between consecutive loops
VALUE_SCALE    = 0.55 # how strongly the growth rate modulates the radius
INTERP_PTS     = 30   # interpolated points per year gap for a smooth curve


def _spiral_xy(
    idx: np.ndarray,
    norm_values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert (year_index, normalised_value) to Cartesian (x, y) coordinates.

    Angle starts at 12 o'clock (−π/2) and advances clockwise so the spiral
    reads like a clock — intuitive for time-based data.

    Parameters
    ----------
    idx         : 1-D float array of year indices (may be non-integer for interpolation)
    norm_values : values normalised to [−0.5, +0.5] so the mean sits at r_base

    Returns
    -------
    x, y arrays in the same shape as idx
    """
    theta  = (idx % YEARS_PER_LOOP) / YEARS_PER_LOOP * 2 * np.pi - np.pi / 2
    r_base = BASE_RADIUS + (idx // YEARS_PER_LOOP) * LOOP_SPACING
    r      = r_base + norm_values * VALUE_SCALE * LOOP_SPACING
    return r * np.cos(theta), r * np.sin(theta)


def build_spiral(
    df: pd.DataFrame,
    year_range: tuple[int, int],
) -> go.Figure:
    """
    Build the GDP growth spiral figure.

    The figure contains three layers:
      1. A smooth interpolated curve — the spiral backbone, coloured by value
      2. Dot markers at the actual annual data points
      3. Text annotations for every other year and key inflection points

    Parameters
    ----------
    df         : Uzbekistan long-format DataFrame (from data_loader.load_uzbekistan)
    year_range : (start_year, end_year) from the dashboard year-range slider

    Returns
    -------
    go.Figure ready to drop into a dcc.Graph component
    """
    from dashboard.data_loader import get_series

    series = get_series(df, "NY.GDP.MKTP.KD.ZG")
    series = series[
        (series["Year"] >= year_range[0]) & (series["Year"] <= year_range[1])
    ].reset_index(drop=True)

    if series.empty:
        return _empty_figure("No GDP growth data for selected range")

    years  = series["Year"].values
    values = series["Value"].values
    n      = len(values)

    # Normalise to [−0.5, +0.5] so the average year sits exactly on r_base
    v_min, v_max = values.min(), values.max()
    norm = (values - v_min) / (v_max - v_min + 1e-9) - 0.5

    idx = np.arange(n, dtype=float)

    # ── Build smooth interpolated path ─────────────────────────────────────
    idx_fine  = np.linspace(0, n - 1, n * INTERP_PTS)
    norm_fine = np.interp(idx_fine, idx, norm)
    val_fine  = np.interp(idx_fine, idx, values)
    x_fine, y_fine = _spiral_xy(idx_fine, norm_fine)

    # ── Actual data point coordinates ─────────────────────────────────────
    x_pts, y_pts = _spiral_xy(idx, norm)

    fig = go.Figure()

    # Layer 1: dense markers forming the gradient spiral — Plotly scatter.line
    # does not support per-point colour arrays, so we use tightly-packed markers
    # (size=3) that visually read as a continuous coloured line.
    fig.add_trace(go.Scatter(
        x    = x_fine,
        y    = y_fine,
        mode = "markers",
        marker = dict(
            size       = 3,
            color      = val_fine,
            colorscale = "RdYlGn",
            cmin       = v_min,
            cmax       = v_max,
            showscale  = False,
        ),
        hoverinfo  = "skip",
        showlegend = False,
    ))

    # Layer 2: annual data points with hover detail
    fig.add_trace(go.Scatter(
        x          = x_pts,
        y          = y_pts,
        mode       = "markers+text",
        marker     = dict(
            size   = 10,
            color  = values,
            colorscale = "RdYlGn",
            cmin   = v_min,
            cmax   = v_max,
            line   = dict(color=BG_PLOT, width=1.5),
            showscale = True,
            colorbar  = dict(
                title     = dict(text="Growth %", font=dict(color=TEXT_COLOR, size=11)),
                tickfont  = dict(color=MUTED, size=10),
                thickness = 12,
                len       = 0.6,
                x         = 1.02,
            ),
        ),
        text       = [str(y) if i % 2 == 0 else "" for i, y in enumerate(years)],
        textposition = "top center",
        textfont   = dict(color=MUTED, size=9),
        customdata = np.column_stack([years, values]),
        hovertemplate = (
            "<b>%{customdata[0]}</b><br>"
            "GDP growth: <b>%{customdata[1]:.2f}%</b><extra></extra>"
        ),
        showlegend = False,
    ))

    # Layer 3: annotate the COVID trough and the 2007 peak if in range
    _add_annotation(fig, x_pts, y_pts, years, values, 2020, "COVID\ndip", HIGHLIGHT)
    _add_annotation(fig, x_pts, y_pts, years, values, 2007, "Peak", ACCENT)

    fig.update_layout(
        paper_bgcolor = BG_PAPER,
        plot_bgcolor  = BG_PLOT,
        title = dict(
            text      = "GDP Growth Spiral  \U0001f1fa\U0001f1ff  Uzbekistan",
            font      = dict(color=TEXT_COLOR, size=16),
            x         = 0.5,
            xanchor   = "center",
        ),
        xaxis = dict(visible=False, scaleanchor="y"),
        yaxis = dict(visible=False),
        margin     = dict(l=20, r=60, t=50, b=20),
        hoverlabel = dict(bgcolor="#1a1d2e", font_color=TEXT_COLOR),
    )
    return fig


def _add_annotation(
    fig: go.Figure,
    x_pts: np.ndarray,
    y_pts: np.ndarray,
    years: np.ndarray,
    values: np.ndarray,
    target_year: int,
    label: str,
    color: str,
) -> None:
    """Add an arrow annotation at a specific year if it falls within the data."""
    mask = years == target_year
    if not mask.any():
        return
    i = int(np.where(mask)[0][0])
    fig.add_annotation(
        x         = x_pts[i],
        y         = y_pts[i],
        text      = f"<b>{label}</b><br>{values[i]:.1f}%",
        showarrow = True,
        arrowhead = 2,
        arrowcolor = color,
        font      = dict(color=color, size=10),
        bgcolor   = "#1a1d2e",
        bordercolor = color,
        ax        = 30,
        ay        = -30,
    )


def _empty_figure(message: str) -> go.Figure:
    """Return a blank figure with a centred message — shown when data is absent."""
    fig = go.Figure()
    fig.add_annotation(
        text      = message,
        x         = 0.5, y = 0.5,
        xref      = "paper", yref = "paper",
        showarrow = False,
        font      = dict(color=MUTED, size=14),
    )
    fig.update_layout(
        paper_bgcolor = BG_PAPER,
        plot_bgcolor  = BG_PLOT,
        xaxis = dict(visible=False),
        yaxis = dict(visible=False),
    )
    return fig
