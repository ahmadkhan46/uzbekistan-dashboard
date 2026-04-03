"""
radar.py — Multi-indicator development profile radar chart

Compares Uzbekistan across 7 development dimensions simultaneously.
When regional data is available, the radar overlays Uzbekistan against
the Europe & Central Asia regional average and Kazakhstan as a peer.

Why a radar for this?  Development is multidimensional — a single country
can lead in electricity access while lagging in CO2 efficiency.  The radar's
polygon shape encodes the full profile at a glance; outlying spokes catch the
eye immediately without requiring the user to scan multiple charts.

Normalisation rationale: each indicator uses a fixed world-plausible min/max
so the score is comparable across indicators.  For CO2 per capita the scale is
inverted (lower emissions = higher score) so all spokes point "outward = better".
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

BG_PAPER   = "rgba(0,0,0,0)"
BG_PLOT    = "rgba(0,0,0,0)"
TEXT_COLOR = "#e8eaf6"
MUTED      = "#8892b0"
GRID_COLOR = "#2a2d3e"

# Colour + display name per entity
ENTITY_STYLES: dict[str, dict] = {
    "Uzbekistan":             {"color": "#4f8ef7", "fill": "rgba(79,142,247,0.25)"},
    "Europe & Central Asia":  {"color": "#2ecc71", "fill": "rgba(46,204,113,0.15)"},
    "Kazakhstan":             {"color": "#f39c12", "fill": "rgba(243,156,18,0.15)"},
}

# Radar spokes: code → (display_label, world_min, world_max, invert)
# invert=True means lower raw value → higher score (e.g. CO2: less is better)
SPOKES: list[tuple[str, str, float, float, bool]] = [
    ("NY.GDP.PCAP.CD",       "GDP /capita",      500,   25000, False),
    ("SP.DYN.LE00.IN",       "Life Expect.",      55,      80, False),
    ("EN.GHG.CO2.PC.CE.AR5", "Low Carbon",         0,      15, True ),
    ("SE.SEC.ENRR",          "Secondary\nEnroll", 30,     110, False),
    ("EG.ELC.ACCS.ZS",       "Electricity\nAccess", 20,  100, False),
    ("EG.FEC.RNEW.ZS",       "Renewables",         0,   60, False),
    ("SP.URB.TOTL.IN.ZS",    "Urban\nPop %",      20,    80, False),
]


def _score(value: float, world_min: float, world_max: float, invert: bool) -> float:
    """
    Normalise a raw indicator value to a 0-100 score using world-plausible bounds.

    Clamping to [0, 100] prevents a single extreme observation from compressing
    all other scores — important for GDP per capita which can spike far above
    the reference max for oil-rich neighbours.

    Inverted indicators (lower raw = better outcome, e.g. CO2) are reflected
    so that the radar's outward = better convention holds uniformly.
    """
    raw_score = (value - world_min) / (world_max - world_min) * 100
    raw_score = float(np.clip(raw_score, 0, 100))
    return 100 - raw_score if invert else raw_score


def _entity_scores(
    df: pd.DataFrame,
    country_name: str,
    year: int,
) -> list[float | None]:
    """
    Extract the 0-100 score for each spoke for a single country and year.

    Returns None for a spoke when the indicator is absent — the caller
    decides whether to skip the entity or substitute a neutral 0.
    """
    from dashboard.data_loader import get_series

    scores: list[float | None] = []
    for code, _, wmin, wmax, inv in SPOKES:
        s = get_series(df, code)
        s = s[s["Country Name"] == country_name]
        row = s[s["Year"] == year]
        if row.empty:
            # Fallback: use the nearest available year within ±3 years
            nearby = s[(s["Year"] >= year - 3) & (s["Year"] <= year + 3)]
            row = nearby.sort_values("Year", key=lambda y: abs(y - year)).head(1)
        if row.empty:
            scores.append(None)
        else:
            scores.append(_score(float(row["Value"].iloc[0]), wmin, wmax, inv))
    return scores


def build_radar(
    uzb_df: pd.DataFrame,
    reg_df: pd.DataFrame,
    year: int,
) -> go.Figure:
    """
    Build the development profile radar chart.

    Shows Uzbekistan's scores on 7 development dimensions for the selected year.
    Overlays regional average and Kazakhstan when regional data is available.

    Parameters
    ----------
    uzb_df : Uzbekistan long-format DataFrame
    reg_df : Regional comparison DataFrame (may be empty if not yet downloaded)
    year   : The selected year (from the year-range slider's end value)

    Returns
    -------
    go.Figure with scatterpolar traces
    """
    labels = [spoke[1] for spoke in SPOKES]
    # Plotly requires the first label repeated at the end to close the polygon
    closed_labels = labels + [labels[0]]

    fig = go.Figure()

    # ── Uzbekistan trace — always shown ────────────────────────────────────
    uzb_scores = _entity_scores(uzb_df, "Uzbekistan", year)
    if any(s is not None for s in uzb_scores):
        filled_scores = [s if s is not None else 0 for s in uzb_scores]
        closed_scores = filled_scores + [filled_scores[0]]
        style = ENTITY_STYLES["Uzbekistan"]
        fig.add_trace(go.Scatterpolar(
            r       = closed_scores,
            theta   = closed_labels,
            fill    = "toself",
            fillcolor = style["fill"],
            line    = dict(color=style["color"], width=2.5),
            name    = f"Uzbekistan ({year})",
            hovertemplate = "<b>%{theta}</b><br>Score: %{r:.1f}/100<extra></extra>",
        ))

    # ── Regional / peer traces — only when data is present ─────────────────
    if not reg_df.empty:
        for entity, style in ENTITY_STYLES.items():
            if entity == "Uzbekistan":
                continue
            scores = _entity_scores(reg_df, entity, year)
            if all(s is None for s in scores):
                continue
            filled = [s if s is not None else 0 for s in scores]
            closed = filled + [filled[0]]
            fig.add_trace(go.Scatterpolar(
                r       = closed,
                theta   = closed_labels,
                fill    = "toself",
                fillcolor = style["fill"],
                line    = dict(color=style["color"], width=1.5, dash="dot"),
                name    = f"{entity} ({year})",
                hovertemplate = "<b>%{theta}</b><br>Score: %{r:.1f}/100<extra></extra>",
            ))
    else:
        # Show a second Uzbekistan trace for the start year to indicate change
        start_year = max(year - 10, 2006)
        start_scores = _entity_scores(uzb_df, "Uzbekistan", start_year)
        if any(s is not None for s in start_scores):
            filled = [s if s is not None else 0 for s in start_scores]
            closed = filled + [filled[0]]
            fig.add_trace(go.Scatterpolar(
                r         = closed,
                theta     = closed_labels,
                fill      = "toself",
                fillcolor = "rgba(136,146,176,0.10)",
                line      = dict(color=MUTED, width=1.5, dash="dot"),
                name      = f"Uzbekistan ({start_year})",
                hovertemplate = "<b>%{theta}</b><br>Score: %{r:.1f}/100<extra></extra>",
            ))

    fig.update_layout(
        polar = dict(
            bgcolor   = "rgba(26,29,46,0.6)",
            radialaxis = dict(
                visible    = True,
                range      = [0, 100],
                ticksuffix = "",
                tickfont   = dict(color=MUTED, size=9),
                gridcolor  = GRID_COLOR,
                linecolor  = GRID_COLOR,
            ),
            angularaxis = dict(
                tickfont  = dict(color=TEXT_COLOR, size=10),
                linecolor = GRID_COLOR,
                gridcolor = GRID_COLOR,
            ),
        ),
        paper_bgcolor = BG_PAPER,
        title = dict(
            text    = f"Development Profile  \U0001f1fa\U0001f1ff  {year}",
            font    = dict(color=TEXT_COLOR, size=16),
            x       = 0.5,
            xanchor = "center",
        ),
        legend = dict(
            font      = dict(color=TEXT_COLOR, size=10),
            bgcolor   = "rgba(26,29,46,0.8)",
            bordercolor = GRID_COLOR,
            x         = 1.05,
        ),
        margin     = dict(l=60, r=120, t=60, b=40),
        hoverlabel = dict(bgcolor="#1a1d2e", font_color=TEXT_COLOR),
    )
    return fig
