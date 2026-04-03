"""
layouts.py — Dashboard layout and page structure.

Visual hierarchy (mirrors professor's sample, adapted for Uzbekistan WDI data):
  Navbar     — flag, title, region metadata, FROM/TO year dropdowns (top-right)
  KPI row    — 5 cards: pop growth, GDP growth, life exp, electricity, infant mortality
               each with a "vs prev decade" delta in green/red
  Main grid  — left 42%: tabbed Spiral / Radar / Choropleth + map indicator selector
               right 58%: "INDICATOR TRENDS" header + 3×2 sparkline grid
  Footer     — indicator codes + framework credits
"""
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc, html

from dashboard.data_loader import (
    INDICATORS, KPI_CODES, KPI_LOWER_IS_BETTER, TREND_CHARTS,
    get_decade_delta, get_latest_values, get_year_range, load_uzbekistan,
)
from dashboard.visualizations.choropleth import CHOROPLETH_INDICATORS

# ── Palette ────────────────────────────────────────────────────────────────
BG     = "#0d1117"
CARD   = "#161b27"
BORDER = "#21273a"
ACCENT = "#4f8ef7"
GREEN  = "#2ecc71"
RED    = "#e74c3c"
AMBER  = "#f39c12"
TEXT   = "#e8eaf6"
MUTED  = "#8892b0"

_CARD = {"backgroundColor": CARD, "border": f"1px solid {BORDER}",
         "borderRadius": "12px", "padding": "16px 18px"}

_LABEL = {"color": MUTED, "fontSize": "0.68rem", "textTransform": "uppercase",
          "letterSpacing": "0.08em", "display": "block", "marginBottom": "6px"}

_KPI_COLORS = [ACCENT, GREEN, "#c778dd", "#1abc9c", "#e74c3c"]

_TAB_BASE = {
    "backgroundColor": BG, "color": MUTED,
    "border": "none", "borderBottom": f"2px solid {BORDER}",
    "padding": "10px 16px", "fontSize": "0.75rem",
    "fontWeight": "500", "letterSpacing": "0.04em",
}
_TAB_SELECTED = {
    **_TAB_BASE, "backgroundColor": CARD,
    "color": ACCENT, "borderBottom": f"2px solid {ACCENT}",
}


# ── Helpers ────────────────────────────────────────────────────────────────
def _fmt(value: float | None, code: str) -> str:
    """Format a KPI value for display, unit-aware (abbreviated for large numbers)."""
    if value is None:
        return "—"
    unit = INDICATORS.get(code, {}).get("unit", "")
    if unit == "US$":
        if value >= 1e9:  return f"${value/1e9:.1f}B"
        if value >= 1e6:  return f"${value/1e6:.1f}M"
        return f"${value:,.0f}"
    if unit == "years": return f"{value:.1f} yrs"
    if unit == "%":     return f"{value:.1f}%"
    if unit == "/1k":   return f"{value:.1f}/1k"
    if value >= 1e6:    return f"{value/1e6:.1f}M"
    return f"{value:,.0f}"


def _delta_display(delta: float | None, code: str) -> html.P:
    """
    Render the KPI delta line ("▲ +2.1 vs prev decade").

    Colour logic: green = improvement, red = deterioration.
    For infant mortality, lower is better so the colours are inverted.
    """
    if delta is None:
        return html.P("no prior-decade data", style={"fontSize": "0.65rem", "color": MUTED, "margin": "4px 0 0"})

    lower_better = KPI_LOWER_IS_BETTER.get(code, False)
    improved = (delta < 0) if lower_better else (delta > 0)
    color  = GREEN if improved else RED
    arrow  = "▲" if delta > 0 else "▼"
    unit   = INDICATORS.get(code, {}).get("unit", "")
    suffix = f" {unit}" if unit and unit not in ("US$",) else ""
    text   = f"{arrow} {abs(delta):+.2f}{suffix} vs prev decade".replace("+-", "")

    return html.P(text, style={"fontSize": "0.65rem", "color": color,
                               "margin": "5px 0 0", "fontWeight": "500"})


# ── KPI card ───────────────────────────────────────────────────────────────
def _kpi_card(code: str, value: float | None, year: int | None,
              delta: float | None, idx: int) -> dbc.Col:
    label  = INDICATORS.get(code, {}).get("label", code).upper()
    colour = _KPI_COLORS[idx % len(_KPI_COLORS)]
    return dbc.Col(
        html.Div([
            html.Div(style={"height": "3px", "borderRadius": "3px 3px 0 0",
                            "backgroundColor": colour, "marginBottom": "10px"}),
            html.P(label, style={"fontSize": "0.72rem", "color": "#c5cee0",
                                 "letterSpacing": "0.07em", "margin": "0 0 6px"}),
            html.P(_fmt(value, code), style={"fontSize": "1.85rem", "fontWeight": "700",
                                             "color": colour, "margin": "0", "lineHeight": "1.1"}),
            html.P(f"as of {year}" if year else "", style={"fontSize": "0.72rem",
                                                           "color": "#8892b0", "margin": "4px 0 0"}),
            _delta_display(delta, code),
        ], style=_CARD),
        xs=6, md=True,  # 5 equal columns
    )


# ── Navbar ─────────────────────────────────────────────────────────────────
def _navbar(year_min: int, year_max: int) -> html.Div:
    """
    Top navigation bar containing branding on the left and year controls on the right.

    Year FROM/TO dropdowns replace the range slider for precision selection —
    the professor's sample uses this two-dropdown pattern to let users jump
    directly to a specific year without dragging.
    """
    year_options = [{"label": str(y), "value": y} for y in range(year_min, year_max + 1)]
    default_to   = min(year_max, 2024)   # 2025 is forward-filled; default to last confirmed

    return html.Div(
        dbc.Container([
            # ── Left: branding block ──────────────────────────────────────
            html.Div([
                html.Span("🇺🇿", style={"fontSize": "2rem", "marginRight": "14px", "lineHeight": "1"}),
                html.Div([
                    html.Div([
                        html.Span("Uzbekistan", style={
                            "color": "#ffffff", "fontWeight": "800",
                            "fontSize": "1.35rem", "letterSpacing": "-0.02em",
                        }),
                        html.Span(" Development Dashboard", style={
                            "color": "#c5cee0", "fontWeight": "300",
                            "fontSize": "1.2rem", "marginLeft": "6px",
                        }),
                    ], style={"display": "flex", "alignItems": "baseline"}),
                    html.P(
                        "Central Asia  ·  World Bank WDI  ·  2006–2024",
                        style={"color": "#8892b0", "fontSize": "0.82rem",
                               "margin": "3px 0 0", "letterSpacing": "0.02em"},
                    ),
                ]),
            ], style={"display": "flex", "alignItems": "center"}),

            # ── Right: year range controls ────────────────────────────────
            html.Div([
                html.Span("YEAR RANGE", style={
                    "color": "#ffffff", "fontSize": "0.88rem",
                    "letterSpacing": "0.10em", "fontWeight": "700",
                    "textTransform": "uppercase", "marginRight": "18px",
                }),
                html.Div([
                    html.Span("FROM", style={
                        "color": "#c5cee0", "fontSize": "0.92rem",
                        "fontWeight": "600", "marginRight": "10px",
                    }),
                    dcc.Dropdown(
                        id="year-from", options=year_options, value=year_min,
                        clearable=False, searchable=False,
                        style={"width": "100px"},
                        className="year-dropdown",
                    ),
                    html.Span("→", style={
                        "color": "#c5cee0", "fontSize": "1.4rem",
                        "margin": "0 16px", "fontWeight": "200",
                    }),
                    html.Span("TO", style={
                        "color": "#c5cee0", "fontSize": "0.92rem",
                        "fontWeight": "600", "marginRight": "10px",
                    }),
                    dcc.Dropdown(
                        id="year-to", options=year_options, value=default_to,
                        clearable=False, searchable=False,
                        style={"width": "100px"},
                        className="year-dropdown",
                    ),
                ], style={"display": "flex", "alignItems": "center"}),
            ], style={"marginLeft": "auto", "display": "flex", "alignItems": "center"}),
        ], fluid=True, style={"display": "flex", "alignItems": "center",
                               "justifyContent": "space-between", "padding": "14px 24px"}),
        style={"backgroundColor": CARD, "borderBottom": f"1px solid {BORDER}",
               "position": "sticky", "top": "0", "zIndex": "1000",
               "boxShadow": "0 2px 20px rgba(0,0,0,0.5)"},
    )


# ── Left panel — tabbed hero visualisations ────────────────────────────────
def _left_panel() -> html.Div:
    """
    Tabbed panel containing the three mandatory hero visualisations.
    All three dcc.Graph elements are always in the DOM; inactive tabs are hidden
    by CSS (display:none).  This means every chart stays pre-rendered and
    switching tabs is instant — no re-render latency.
    """
    graph_cfg = {"displayModeBar": False, "responsive": True}

    map_options = [{"label": m["label"], "value": c}
                   for c, m in CHOROPLETH_INDICATORS.items()]

    return html.Div([
        dcc.Tabs(
            id="viz-tabs", value="spiral",
            style={"borderBottom": f"1px solid {BORDER}"},
            colors={"border": BORDER, "primary": ACCENT, "background": BG},
            children=[
                dcc.Tab(label="Spiral Graph",   value="spiral",
                        style=_TAB_BASE, selected_style=_TAB_SELECTED, children=[
                    html.P("GDP GROWTH (ANNUAL %)  ·  NY.GDP.MKTP.KD.ZG",
                           style={"color": MUTED, "fontSize": "0.62rem",
                                  "letterSpacing": "0.06em", "margin": "10px 0 0 14px"}),
                    dcc.Graph(id="spiral-chart", config=graph_cfg,
                              style={"height": "470px"}),
                ]),
                dcc.Tab(label="Radar Plot",     value="radar",
                        style=_TAB_BASE, selected_style=_TAB_SELECTED, children=[
                    html.P("7-INDICATOR DEVELOPMENT PROFILE  ·  NORMALISED 0–100",
                           style={"color": MUTED, "fontSize": "0.62rem",
                                  "letterSpacing": "0.06em", "margin": "10px 0 0 14px"}),
                    dcc.Graph(id="radar-chart", config=graph_cfg,
                              style={"height": "470px"}),
                ]),
                dcc.Tab(label="Geospatial Map", value="choropleth",
                        style=_TAB_BASE, selected_style=_TAB_SELECTED, children=[
                    html.P("CENTRAL ASIA  ·  NATURAL EARTH PROJECTION",
                           style={"color": MUTED, "fontSize": "0.62rem",
                                  "letterSpacing": "0.06em", "margin": "10px 0 0 14px"}),
                    dcc.Graph(id="choropleth-chart", config=graph_cfg,
                              style={"height": "435px"}),
                    html.Div([
                        html.Label("Map Indicator", style={**_LABEL, "marginBottom": "4px"}),
                        dcc.Dropdown(
                            id="choropleth-indicator", options=map_options,
                            value="NY.GDP.PCAP.PP.CD", clearable=False,
                            style={"backgroundColor": BG, "color": TEXT,
                                   "border": f"1px solid {BORDER}"},
                            className="dark-select",
                        ),
                    ], style={"padding": "10px 14px 14px"}),
                ]),
            ],
        ),
    ], style={**_CARD, "padding": "0"})


# ── Right panel — indicator trends grid ────────────────────────────────────
def _trend_cell(trend_id: str, label: str, color: str) -> dbc.Col:
    """One sparkline cell: readable label + spacious dcc.Graph."""
    return dbc.Col(
        html.Div([
            html.P(label.upper(), className="trend-label",
                   style={"color": TEXT, "fontSize": "0.8rem", "fontWeight": "600",
                          "letterSpacing": "0.06em", "margin": "0 0 6px",
                          "textTransform": "uppercase"}),
            html.Div(style={"height": "3px", "width": "36px", "borderRadius": "2px",
                            "backgroundColor": color, "marginBottom": "10px"}),
            dcc.Graph(id=trend_id,
                      config={"displayModeBar": False, "responsive": True},
                      style={"height": "210px"}),
        ], className="trend-card",
           style={**_CARD, "padding": "18px 16px 10px", "borderRadius": "10px"}),
        md=6,   # 2 cards per row → 3 rows of 2 within the full-width panel
    )


def _right_panel() -> html.Div:
    """
    6-chart indicator trends grid: 3 rows × 2 columns.

    The panel itself spans the full page width (placed in a md=12 row).
    Inside it, each sparkline card is md=6 so exactly two sit side-by-side,
    giving three inner rows — spacious and easy to read.
    """
    rows = []
    for i in range(0, len(TREND_CHARTS), 2):
        pair = TREND_CHARTS[i: i + 2]
        cols = [
            _trend_cell(f"trend-{i + k}", pair[k][1], pair[k][3])
            for k in range(len(pair))
        ]
        rows.append(dbc.Row(cols, className="g-3 mb-3"))

    return html.Div([
        html.Div([
            html.Span("INDICATOR TRENDS", style={
                "color": TEXT, "fontSize": "0.85rem", "fontWeight": "700",
                "letterSpacing": "0.09em",
            }),
            html.Span(id="trends-title", style={
                "color": MUTED, "fontSize": "0.82rem", "marginLeft": "12px",
            }),
        ], style={"marginBottom": "16px", "paddingBottom": "10px",
                  "borderBottom": f"1px solid {BORDER}"}),
        *rows,
    ], style={**_CARD, "padding": "24px 22px"})


# ── Footer ─────────────────────────────────────────────────────────────────
def _footer() -> html.Div:
    codes = "  ·  ".join(INDICATORS.keys())
    return html.Div([
        html.P(f"Indicators: {codes}", style={
            "color": MUTED, "fontSize": "0.62rem", "marginBottom": "4px",
        }),
        html.P(
            "Framework: Dash (Python)  ·  Charts: Plotly  ·  "
            "Data: World Bank World Development Indicators (WDI)  ·  "
            "Country: Uzbekistan (UZB)  ·  databank.worldbank.org",
            style={"color": MUTED, "fontSize": "0.62rem"},
        ),
    ], style={"borderTop": f"1px solid {BORDER}", "padding": "14px 0 8px",
              "marginTop": "4px"})


# ── Main assembler ──────────────────────────────────────────────────────────
def build_layout() -> html.Div:
    """
    Assemble the complete dashboard layout.

    KPI values and deltas are computed once at server startup and embedded
    in the layout as static HTML.  Only the charts (spiral, radar, choropleth,
    6 trend sparklines) are dynamic and driven by callbacks.
    """
    uzb_df    = load_uzbekistan()
    kpi_vals  = get_latest_values(uzb_df, KPI_CODES)
    year_min, year_max = get_year_range(uzb_df)

    kpi_row = dbc.Row(
        [
            _kpi_card(
                code  = code,
                value = val,
                year  = yr,
                delta = get_decade_delta(uzb_df, code, yr) if yr else None,
                idx   = i,
            )
            for i, (code, (val, yr)) in enumerate(kpi_vals.items())
        ],
        className="g-2 mb-3",
    )

    return html.Div([
        _navbar(year_min, year_max),
        dbc.Container([
            html.Div(style={"height": "16px"}),
            kpi_row,
            # Hero visualisations — full width
            dbc.Row([
                dbc.Col(_left_panel(), md=12, className="mb-3"),
            ], className="g-3"),
            # Indicator trends — full width, own row below
            dbc.Row([
                dbc.Col(_right_panel(), md=12, className="mb-3"),
            ], className="g-3"),
            _footer(),
        ], fluid=True, style={"padding": "0 24px"}),
    ], style={
        "backgroundColor": BG,
        "minHeight"      : "100vh",
        "fontFamily"     : "'Inter', -apple-system, sans-serif",
        "color"          : TEXT,
    })
