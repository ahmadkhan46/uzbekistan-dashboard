"""
app.py — Uzbekistan WDI Development Dashboard entry point

Initialises the Dash application, mounts the layout, and registers callbacks.
Run with:  python dashboard/app.py

Why a separate app.py rather than inline in layouts.py?
Keeping initialisation here prevents circular imports — callbacks.py and
layouts.py both import `app`, so they must import from a module that holds
no heavy logic of its own.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from the project root: python dashboard/app.py
sys.path.insert(0, str(Path(__file__).parent.parent))

import dash
import dash_bootstrap_components as dbc

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],   # dark Bootstrap base eliminates white flash
    title="Uzbekistan Development Dashboard",
    # Suppress initial callback errors — charts render empty until data loads
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server   # exposed for gunicorn deployment

# ── Import layout and callbacks AFTER app is created to avoid circular deps ──
from dashboard import layouts, callbacks  # noqa: E402, F401

app.layout = layouts.build_layout()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
