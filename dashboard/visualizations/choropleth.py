"""
choropleth.py — Geospatial indicator map for Uzbekistan and Central Asia

When regional data is available: colours all Central Asian countries by the
selected indicator for the selected year, with Uzbekistan outlined prominently.

When only Uzbekistan data exists: renders Uzbekistan as a single highlighted
polygon on a natural-earth global basemap — still a valid geospatial story
that places Uzbekistan in geographic context.

Why go.Choropleth over choropleth_mapbox?  go.Choropleth with natural-earth
projection requires no Mapbox token, works offline, and the central-Asia
region looks far better on an equal-earth projection than on Mercator tiles.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

BG_PAPER   = "rgba(0,0,0,0)"
TEXT_COLOR = "#e8eaf6"
MUTED      = "#8892b0"
OCEAN      = "#0d1117"
LAND       = "#1e2235"
UZB_BORDER = "#f39c12"   # amber outline makes Uzbekistan unmissable

# Indicators available for the choropleth and their display names / units
CHOROPLETH_INDICATORS: dict[str, dict] = {
    "NY.GDP.PCAP.PP.CD":      {"label": "GDP per capita, PPP (Int$)",   "colorscale": "Blues"},
    "EG.ELC.ACCS.ZS":         {"label": "Access to electricity (%)",    "colorscale": "YlGnBu"},
    "EN.GHG.CO2.PC.CE.AR5":   {"label": "CO2 per capita (t CO2e)",      "colorscale": "Reds"},
    "EG.FEC.RNEW.ZS":         {"label": "Renewable energy (%)",         "colorscale": "Greens"},
    "SP.URB.TOTL.IN.ZS":      {"label": "Urban population (%)",         "colorscale": "Purp"},
}

# ISO-3 country codes and display names for Central Asian countries in the data
CENTRAL_ASIA: dict[str, str] = {
    "UZB": "Uzbekistan",
    "KAZ": "Kazakhstan",
    "KGZ": "Kyrgyz Republic",
    "TJK": "Tajikistan",
    "TKM": "Turkmenistan",
}


def build_choropleth(
    uzb_df: pd.DataFrame,
    reg_df: pd.DataFrame,
    indicator_code: str,
    year: int,
) -> go.Figure:
    """
    Build the choropleth map figure.

    If regional data exists, colours all five Central Asian countries.
    Otherwise highlights only Uzbekistan against a neutral global basemap.

    Parameters
    ----------
    uzb_df         : Uzbekistan long-format DataFrame
    reg_df         : Regional comparison DataFrame (may be empty)
    indicator_code : WDI Series Code to visualise
    year           : Selected year

    Returns
    -------
    go.Figure with a go.Choropleth trace
    """
    from dashboard.data_loader import get_series, indicator_label, indicator_unit

    ind_meta  = CHOROPLETH_INDICATORS.get(indicator_code, {})
    ind_label = ind_meta.get("label", indicator_label(indicator_code))
    colorscale = ind_meta.get("colorscale", "Blues")
    unit       = indicator_unit(indicator_code)

    fig = go.Figure()

    if not reg_df.empty:
        # ── Multi-country: colour all Central Asian countries ──────────────
        rows = []
        combined = pd.concat([uzb_df, reg_df], ignore_index=True)
        for iso, name in CENTRAL_ASIA.items():
            s = get_series(combined, indicator_code)
            s = s[s["Country Name"] == name]
            row = s[s["Year"] == year]
            if row.empty:
                nearby = s[(s["Year"] >= year - 3) & (s["Year"] <= year + 3)]
                row = nearby.sort_values("Year", key=lambda y: abs(y - year)).head(1)
            if not row.empty:
                rows.append({
                    "iso"  : iso,
                    "name" : name,
                    "value": float(row["Value"].iloc[0]),
                })

        if rows:
            iso_codes = [r["iso"]   for r in rows]
            names     = [r["name"]  for r in rows]
            z_values  = [r["value"] for r in rows]

            fig.add_trace(go.Choropleth(
                locations   = iso_codes,
                z           = z_values,
                text        = names,
                colorscale  = colorscale,
                colorbar    = _colorbar(ind_label, unit),
                marker      = dict(
                    line=dict(
                        color = [UZB_BORDER if c == "UZB" else "#2a2d3e" for c in iso_codes],
                        width = [3          if c == "UZB" else 0.5       for c in iso_codes],
                    )
                ),
                hovertemplate = (
                    "<b>%{text}</b><br>"
                    f"{ind_label}: " + "%{z:,.1f}" + f" {unit}<extra></extra>"
                ),
                showscale   = True,
            ))
    else:
        # ── Uzbekistan only: grey neighbour outlines + Uzbekistan filled ───
        s = get_series(uzb_df, indicator_code)
        row = s[s["Year"] == year]
        if row.empty:
            nearby = s[(s["Year"] >= year - 3) & (s["Year"] <= year + 3)]
            row = nearby.sort_values("Year", key=lambda y: abs(y - year)).head(1)

        uzb_value = float(row["Value"].iloc[0]) if not row.empty else None

        # Neighbour countries as neutral grey polygons — geographic context only
        neighbours = [c for c in CENTRAL_ASIA if c != "UZB"]
        fig.add_trace(go.Choropleth(
            locations  = neighbours,
            z          = [0] * len(neighbours),
            colorscale = [[0, "#2a2d3e"], [1, "#2a2d3e"]],
            showscale  = False,
            marker     = dict(line=dict(color="#1e2235", width=0.5)),
            hoverinfo  = "skip",
        ))

        if uzb_value is not None:
            fig.add_trace(go.Choropleth(
                locations   = ["UZB"],
                z           = [uzb_value],
                text        = ["Uzbekistan"],
                colorscale  = colorscale,
                showscale   = True,
                colorbar    = _colorbar(ind_label, unit),
                marker      = dict(line=dict(color=UZB_BORDER, width=2.5)),
                hovertemplate = (
                    "<b>Uzbekistan</b><br>"
                    f"{ind_label}: " + "%{z:,.1f}" + f" {unit}<extra></extra>"
                ),
            ))

    fig.update_geos(
        projection_type     = "natural earth",
        showcoastlines      = True,
        coastlinecolor      = "#2a2d3e",
        showland            = True,
        landcolor           = LAND,
        showocean           = True,
        oceancolor          = OCEAN,
        showlakes           = True,
        lakecolor           = OCEAN,
        showframe           = False,
        # Zoom to Central Asia region for maximum Uzbekistan prominence
        center              = dict(lat=42, lon=63),
        lataxis_range       = [30, 60],
        lonaxis_range       = [45, 90],
    )
    fig.update_layout(
        paper_bgcolor = BG_PAPER,
        title = dict(
            text    = f"{ind_label}  \U0001f1fa\U0001f1ff  {year}",
            font    = dict(color=TEXT_COLOR, size=16),
            x       = 0.5,
            xanchor = "center",
        ),
        margin     = dict(l=0, r=0, t=50, b=0),
        hoverlabel = dict(bgcolor="#1a1d2e", font_color=TEXT_COLOR),
        geo        = dict(bgcolor=BG_PAPER),
    )
    return fig


def _colorbar(label: str, unit: str) -> dict:
    """Return a styled colorbar config matching the dark theme."""
    return dict(
        title     = dict(
            text  = f"{label}\n{unit}",
            font  = dict(color=TEXT_COLOR, size=11),
        ),
        tickfont  = dict(color=MUTED, size=10),
        bgcolor   = "rgba(26,29,46,0.8)",
        bordercolor = "#2a2d3e",
        thickness = 14,
        len       = 0.7,
    )
