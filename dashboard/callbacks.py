"""
callbacks.py — All Dash callback functions.

Architecture: DataFrames live in server memory (_CACHE in data_loader.py).
Callbacks receive only lightweight parameters from the browser:
  - year_from / year_to : int   — two integers, ~8 bytes each
  - indicator           : str   — ~25 bytes

This keeps every slider/dropdown interaction near-instant regardless of
dataset size.  No dcc.Store is used — serialising the full DataFrame through
the browser (~1.6 MB) would freeze the year controls on every interaction.

Callback groupings:
  1. Year dropdown sync   — prevents FROM > TO invalid state
  2. Hero charts          — spiral, radar, choropleth (3 separate outputs)
  3. Trend sparklines     — all 6 in one multi-output callback to save roundtrips
  4. Trends panel title   — updates the "2006 → 2024" header text
"""
from __future__ import annotations

from dash import Input, Output, State, callback

from dashboard.data_loader import (
    TREND_CHARTS, get_year_range, load_regional, load_uzbekistan,
)
from dashboard.visualizations.choropleth import build_choropleth
from dashboard.visualizations.radar      import build_radar
from dashboard.visualizations.spiral     import build_spiral
from dashboard.visualizations.trends     import build_trend_chart


# ── 1. Year dropdown sync ──────────────────────────────────────────────────
@callback(
    Output("year-to", "options"),
    Output("year-to", "value"),
    Input("year-from", "value"),
    State("year-to",   "value"),
)
def sync_year_to(year_from: int, current_to: int) -> tuple[list, int]:
    """
    Restrict the TO dropdown to only show years ≥ FROM.

    Without this guard, a user could select FROM=2020, TO=2010, which would
    produce empty charts and a confusing year-range display.  By rebuilding
    the TO options list whenever FROM changes, the invalid range is impossible.
    """
    _, data_max = get_year_range(load_uzbekistan())
    options = [{"label": str(y), "value": y} for y in range(year_from, data_max + 1)]
    # If the current TO fell below the new FROM, snap it forward to FROM
    new_to = current_to if current_to >= year_from else year_from
    return options, new_to


# ── 2. Hero charts ─────────────────────────────────────────────────────────
@callback(
    Output("spiral-chart", "figure"),
    Input("year-from",     "value"),
    Input("year-to",       "value"),
)
def update_spiral(year_from: int, year_to: int) -> object:
    """Rebuild the GDP growth spiral for the selected year range."""
    return build_spiral(load_uzbekistan(), (year_from, year_to))


@callback(
    Output("radar-chart", "figure"),
    Input("year-from",    "value"),
    Input("year-to",      "value"),
)
def update_radar(year_from: int, year_to: int) -> object:
    """
    Show the development profile radar for the END year of the selected range.

    The end year is used (not the start) because it reflects the most current
    state of Uzbekistan's development — the radar is a snapshot, not a trend.
    """
    return build_radar(load_uzbekistan(), load_regional(), year=year_to)


@callback(
    Output("choropleth-chart",    "figure"),
    Input("year-from",            "value"),
    Input("year-to",              "value"),
    Input("choropleth-indicator", "value"),
)
def update_choropleth(year_from: int, year_to: int, indicator: str) -> object:
    """Rebuild the Central Asia choropleth for the selected indicator and end year."""
    return build_choropleth(
        load_uzbekistan(), load_regional(), indicator, year=year_to,
    )


# ── 3. Trend sparklines — all 6 in one call ────────────────────────────────
@callback(
    Output("trend-0", "figure"),
    Output("trend-1", "figure"),
    Output("trend-2", "figure"),
    Output("trend-3", "figure"),
    Output("trend-4", "figure"),
    Output("trend-5", "figure"),
    Input("year-from", "value"),
    Input("year-to",   "value"),
)
def update_trends(year_from: int, year_to: int) -> tuple:
    """
    Rebuild all six indicator sparklines in a single callback.

    One multi-output callback is used instead of six separate callbacks because
    all six charts share identical inputs (year_from, year_to) and read from the
    same cached DataFrame — batching them avoids six redundant round-trips to
    the server when the year dropdowns change.
    """
    uzb    = load_uzbekistan()
    yr     = (year_from, year_to)
    return tuple(
        build_trend_chart(uzb, code, label, unit, color, yr)
        for code, label, unit, color in TREND_CHARTS
    )


# ── 4. Trends panel dynamic title ──────────────────────────────────────────
@callback(
    Output("trends-title", "children"),
    Input("year-from",     "value"),
    Input("year-to",       "value"),
)
def update_trends_title(year_from: int, year_to: int) -> str:
    """Update the 'INDICATOR TRENDS · 2006 → 2024' header text."""
    return f"·  {year_from} → {year_to}"
