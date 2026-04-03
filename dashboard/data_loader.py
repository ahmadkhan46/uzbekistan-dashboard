"""
Runtime data loader for the Uzbekistan WDI dashboard.

All functions read from cleaned_data/ — never from original_data/.

Data is loaded once at server startup and held in _CACHE.  Callbacks receive
only lightweight parameters (year integers, indicator codes) — never DataFrames.
This keeps the browser payload near-zero so the year slider responds instantly.

All WDI Series Codes used by the dashboard are centralised in INDICATORS so
that adding a new metric requires one edit here, not a hunt across callbacks.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# File paths — relative to this file so the project is portable across machines
# ---------------------------------------------------------------------------
_DASH_DIR   = Path(__file__).parent
ROOT        = _DASH_DIR.parent
CLEANED_DIR = ROOT / "cleaned_data"

_UZB_FILE = CLEANED_DIR / "uzbekistan_cleaned.csv"
_REG_FILE = CLEANED_DIR / "central_asia_cleaned.csv"  # written by clean_data.py after regional download

# ---------------------------------------------------------------------------
# Indicator registry — single source of truth for every Series Code used
# ---------------------------------------------------------------------------
INDICATORS: dict[str, dict] = {
    # ── Economic ────────────────────────────────────────────────────────────
    "NY.GDP.MKTP.CD":    {"label": "GDP (current US$)",            "unit": "US$",   "topic": "economic"},
    "NY.GDP.MKTP.KD.ZG": {"label": "GDP growth (annual %)",        "unit": "%",     "topic": "economic"},
    "NY.GDP.PCAP.CD":    {"label": "GDP per capita (current US$)", "unit": "US$",   "topic": "economic"},
    "NY.GDP.PCAP.PP.CD": {"label": "GDP per capita, PPP",          "unit": "Int$",  "topic": "economic"},
    "NY.GNP.PCAP.CD":    {"label": "GNI per capita (Atlas)",       "unit": "US$",   "topic": "economic"},
    "NE.TRD.GNFS.ZS":   {"label": "Trade (% of GDP)",             "unit": "%",     "topic": "economic"},
    "FP.CPI.TOTL.ZG":   {"label": "Inflation (consumer prices %)", "unit": "%",     "topic": "economic"},
    # ── Health & Demographics ───────────────────────────────────────────────
    "SP.DYN.LE00.IN":    {"label": "Life expectancy (years)",      "unit": "years", "topic": "health"},
    "SP.DYN.IMRT.IN":    {"label": "Infant mortality (per 1,000)", "unit": "/1k",   "topic": "health"},
    "SP.DYN.TFRT.IN":    {"label": "Fertility rate (births/woman)","unit": "",      "topic": "health"},
    "SP.POP.GROW":        {"label": "Population growth (%)",        "unit": "%",     "topic": "health"},
    "SP.POP.TOTL":        {"label": "Population, total",            "unit": "",      "topic": "health"},
    "SP.URB.TOTL.IN.ZS": {"label": "Urban population (%)",         "unit": "%",     "topic": "health"},
    # ── Energy & Environment ────────────────────────────────────────────────
    # EN.ATM.CO2E.PC not in WDI export — using the GHG inventory equivalent (AR5 basis)
    "EN.GHG.CO2.PC.CE.AR5": {"label": "CO2 per capita (t CO2e)",     "unit": "t",     "topic": "energy"},
    "EG.ELC.ACCS.ZS":   {"label": "Access to electricity (%)",    "unit": "%",     "topic": "energy"},
    "EG.FEC.RNEW.ZS":   {"label": "Renewable energy (%)",         "unit": "%",     "topic": "energy"},
    "EG.USE.COMM.FO.ZS": {"label": "Fossil fuel consumption (%)", "unit": "%",     "topic": "energy"},
    # ── Education ───────────────────────────────────────────────────────────
    "SE.PRM.ENRR":        {"label": "Primary school enrollment (%)", "unit": "%",   "topic": "education"},
    "SE.SEC.ENRR":        {"label": "Secondary enrollment (%)",      "unit": "%",   "topic": "education"},
    "SE.XPD.TOTL.GD.ZS": {"label": "Education expenditure (% GDP)", "unit": "%",   "topic": "education"},
}

# Indicators used in the radar chart — must be present in both UZB and regional files
RADAR_CODES = [
    "NY.GDP.PCAP.CD",
    "SP.DYN.LE00.IN",
    "EN.GHG.CO2.PC.CE.AR5",
    "SE.SEC.ENRR",
    "EG.ELC.ACCS.ZS",
    "EG.FEC.RNEW.ZS",
    "SP.URB.TOTL.IN.ZS",
]

# Five KPI summary cards shown at the top — ordered by narrative flow:
# population → economic growth → social development → energy → health outcome
KPI_CODES: list[str] = [
    "SP.POP.GROW",        # Population growth rate (%)
    "NY.GDP.MKTP.KD.ZG",  # GDP growth rate (%)
    "SP.DYN.LE00.IN",     # Life expectancy at birth (years)
    "EG.ELC.ACCS.ZS",     # Access to electricity (%)
    "SP.DYN.IMRT.IN",     # Infant mortality (per 1,000 live births)
]

# For KPI delta colouring: True means a *decrease* is good (e.g. infant mortality)
KPI_LOWER_IS_BETTER: dict[str, bool] = {
    "SP.POP.GROW":       False,
    "NY.GDP.MKTP.KD.ZG": False,
    "SP.DYN.LE00.IN":    False,
    "EG.ELC.ACCS.ZS":    False,
    "SP.DYN.IMRT.IN":    True,
}

# Six trend sparkline charts in the right panel — (code, label, unit, accent colour)
TREND_CHARTS: list[tuple[str, str, str, str]] = [
    ("NY.GDP.MKTP.KD.ZG",    "GDP Growth",        "%",     "#2ecc71"),
    ("NY.GDP.PCAP.CD",        "GDP per Capita",    "US$",   "#4f8ef7"),
    ("SP.DYN.LE00.IN",        "Life Expectancy",   "years", "#c778dd"),
    ("SP.DYN.IMRT.IN",        "Infant Mortality",  "/1k",   "#e74c3c"),
    ("EG.ELC.ACCS.ZS",       "Electricity Access","%",     "#1abc9c"),
    ("EN.GHG.CO2.PC.CE.AR5", "CO\u2082 per Capita","t",    "#f39c12"),
]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# In-memory cache — populated once at first call, reused on every callback
# ---------------------------------------------------------------------------
_CACHE: dict[str, pd.DataFrame] = {}


def load_uzbekistan() -> pd.DataFrame:
    """
    Return the cleaned Uzbekistan WDI DataFrame, loading from disk only once.

    Subsequent calls return the same object from _CACHE — zero disk I/O and
    zero JSON serialization, keeping every callback payload tiny.
    """
    if "uzb" not in _CACHE:
        _CACHE["uzb"] = pd.read_csv(_UZB_FILE, encoding="utf-8")
    return _CACHE["uzb"]


def load_regional() -> pd.DataFrame:
    """
    Return the cleaned regional comparison DataFrame (cached after first load).

    Returns an empty DataFrame when the regional file does not yet exist so
    the dashboard renders gracefully while awaiting the Central Asia download.
    """
    if "reg" not in _CACHE:
        if not _REG_FILE.exists():
            _CACHE["reg"] = pd.DataFrame(
                columns=["Country Name", "Country Code",
                         "Series Name", "Series Code", "Year", "Value"]
            )
        else:
            _CACHE["reg"] = pd.read_csv(_REG_FILE, encoding="utf-8")
    return _CACHE["reg"]


# ---------------------------------------------------------------------------
# Accessors used directly by callbacks
# ---------------------------------------------------------------------------
def get_series(df: pd.DataFrame, code: str) -> pd.DataFrame:
    """
    Filter a long-format DataFrame to a single indicator series.

    Parameters
    ----------
    df   : long-format WDI DataFrame (from load_uzbekistan or load_regional)
    code : WDI Series Code e.g. 'NY.GDP.MKTP.KD.ZG'

    Returns
    -------
    DataFrame with columns [Country Name, Year, Value], sorted by Year,
    NaN rows dropped.  Empty DataFrame if the code is not in df.
    """
    return (
        df[df["Series Code"] == code][["Country Name", "Year", "Value"]]
        .dropna(subset=["Value"])
        .sort_values(["Country Name", "Year"])
        .reset_index(drop=True)
    )


def get_latest_values(
    df: pd.DataFrame, codes: list[str]
) -> dict[str, tuple[float | None, int | None]]:
    """
    Extract the most recent non-null value for each indicator code.
    Used to populate the KPI summary cards at dashboard startup.

    Parameters
    ----------
    df    : Uzbekistan long-format DataFrame
    codes : list of WDI Series Codes

    Returns
    -------
    dict mapping code → (value, year) — either may be None if no data exists.
    """
    result: dict[str, tuple[float | None, int | None]] = {}
    for code in codes:
        series = get_series(df, code)
        if not series.empty:
            latest = series.iloc[-1]
            result[code] = (float(latest["Value"]), int(latest["Year"]))
        else:
            result[code] = (None, None)
    return result


def get_year_range(df: pd.DataFrame) -> tuple[int, int]:
    """
    Return the (min_year, max_year) of non-null data in the DataFrame.
    Drives the default bounds of the year-range slider.
    """
    valid = df.dropna(subset=["Value"])
    return int(valid["Year"].min()), int(valid["Year"].max())


def indicator_label(code: str) -> str:
    """Return the human-readable label for a Series Code, or the code itself."""
    return INDICATORS.get(code, {}).get("label", code)


def indicator_unit(code: str) -> str:
    """Return the unit string for a Series Code (empty string if dimensionless)."""
    return INDICATORS.get(code, {}).get("unit", "")


def get_decade_delta(
    df: pd.DataFrame,
    code: str,
    latest_year: int,
) -> float | None:
    """
    Compute the absolute change in an indicator over the most recent ~10 years.

    Looks for the value exactly 10 years prior; if missing, accepts any data
    point within ±2 years.  Returns None when no prior-decade value exists so
    the caller can suppress the delta display rather than show a misleading number.

    Parameters
    ----------
    df          : Uzbekistan long-format DataFrame
    code        : WDI Series Code
    latest_year : The year of the current (latest) value

    Returns
    -------
    float delta (positive = increase, negative = decrease), or None
    """
    series = get_series(df, code)
    curr   = series[series["Year"] == latest_year]
    if curr.empty:
        curr = series.tail(1)
    if curr.empty:
        return None
    curr_val = float(curr["Value"].iloc[0])

    decade_ago = latest_year - 10
    prior = series[series["Year"] == decade_ago]
    if prior.empty:
        # Tolerate a ±2 year gap — covers forward-filled or sparse series
        nearby = series[
            (series["Year"] >= decade_ago - 2) &
            (series["Year"] <= decade_ago + 2)
        ]
        prior = nearby.sort_values("Year").head(1)
    if prior.empty:
        return None
    return curr_val - float(prior["Value"].iloc[0])


def regional_data_available() -> bool:
    """True if the cleaned regional file exists and is non-empty."""
    return _REG_FILE.exists() and _REG_FILE.stat().st_size > 0
