"""
WDI Data Cleaning Pipeline — run once before launching the dashboard.

Reads  : original_data/uzbekistan_wdi_raw.csv
         original_data/uzbekistan_wdi_environment_economy.csv
         original_data/central_asia_comparison.csv  (once downloaded)
Writes : cleaned_data/uzbekistan_cleaned.csv   (Uzbekistan long format)
         cleaned_data/central_asia_cleaned.csv  (regional long format, when available)

Cleaning steps (documented for code-defence):
  Step 1  — Exploration  : print raw shape, null profile, year range
  Step 2A — Missing vals  : forward-fill gaps <= MAX_GAP_FILL years; drop >40% missing
  Step 2B — Type coercion : values -> float64, strip whitespace from string cols
  Step 3  — Reshape       : wide (year cols) -> long (Year, Value)
  Step 4  — Save
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
ORIG = ROOT / "original_data"
OUT  = ROOT / "cleaned_data"

# Input files — both merged into one Uzbekistan cleaned file
UZB_SOURCES = [
    ORIG / "uzbekistan_wdi_raw.csv",
    ORIG / "uzbekistan_wdi_environment_economy.csv",
]
REG_SOURCE  = ORIG / "central_asia_comparison.csv"   # added when Download B arrives

UZB_OUT     = OUT / "uzbekistan_cleaned.csv"
REG_OUT     = OUT / "central_asia_cleaned.csv"

MISSING_SENTINEL = ".."   # WDI uses ".." (not NaN) in exported CSVs
MAX_GAP_FILL     = 3      # forward-fill at most this many consecutive NaN years
MAX_MISSING_RATE = 0.40   # drop a series if >40% of its years remain NaN after fill


# ---------------------------------------------------------------------------
# Step 1 — Exploration
# ---------------------------------------------------------------------------
def step1_explore(df: pd.DataFrame, year_cols: list[str], label: str) -> None:
    """
    Print raw data profile. Nothing is changed — pure observation for the log.
    Documented per-file so each source's quality is independently recorded.
    """
    print(f"  [{label}]  {df.shape[0]} rows x {df.shape[1]} cols")
    countries = df["Country Name"].dropna().unique()
    print(f"    Countries    : {sorted(countries)}")
    print(f"    Year range   : {year_cols[0]} to {year_cols[-1]} ({len(year_cols)} years)")
    uzb_rows = (df["Country Code"] == "UZB").sum()
    sentinel  = (df[year_cols] == MISSING_SENTINEL).sum().sum()
    total_cells = uzb_rows * len(year_cols)
    pct = sentinel / total_cells * 100 if total_cells else 0
    print(f"    UZB rows     : {uzb_rows}")
    print(f"    Missing (..) : {sentinel:,} / {total_cells:,} cells ({pct:.1f}%)")


# ---------------------------------------------------------------------------
# Step 2B — Type coercion
# ---------------------------------------------------------------------------
def step2b_fix_types(df: pd.DataFrame, year_cols: list[str]) -> pd.DataFrame:
    """
    Issue B: WDI exports all cells as strings; year columns contain the '..'
    sentinel for missing values rather than NaN.

    Actions:
    1. Strip whitespace from string ID columns — WDI pads some country names.
    2. Replace '..' sentinel with NaN explicitly before numeric conversion.
    3. Coerce each year column to float64; non-numeric residuals become NaN
       via errors='coerce' rather than raising.
    """
    for col in ["Country Name", "Country Code", "Series Name", "Series Code"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    for col in year_cols:
        df[col] = df[col].replace(MISSING_SENTINEL, np.nan)
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ---------------------------------------------------------------------------
# Step 3 — Reshape wide -> long
# ---------------------------------------------------------------------------
def step3_reshape(df: pd.DataFrame, year_cols: list[str]) -> pd.DataFrame:
    """
    Melt WDI's wide format (one column per year) to long format
    (one row per country-series-year triple).

    Long format is required by Dash callbacks: filtering by a Year slider
    is O(1) on a 'Year' column versus O(n_cols) scanning wide columns.

    Output schema:
        Country Name | Country Code | Series Name | Series Code | Year | Value
    """
    id_cols = ["Country Name", "Country Code", "Series Name", "Series Code"]

    long = df.melt(
        id_vars    = id_cols,
        value_vars = year_cols,
        var_name   = "year_label",   # e.g. "2006 [YR2006]"
        value_name = "Value",
    )
    # Extract the 4-digit integer year from the label — "2006 [YR2006]" -> 2006
    long["Year"] = long["year_label"].str.extract(r"(\d{4})").astype(int)
    return long.drop(columns=["year_label"])[id_cols + ["Year", "Value"]]


# ---------------------------------------------------------------------------
# Step 2A — Missing value handling
# ---------------------------------------------------------------------------
def step2a_handle_missing(long: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Issue A: WDI Uzbekistan data has many NaN gaps, especially before 2010
    when statistical reporting was inconsistent post-independence.

    Strategy:
      1. Forward-fill within each (Country, Series) group for gaps <= MAX_GAP_FILL.
         Appropriate for slowly-varying indicators (life expectancy, electricity
         access). Has minimal effect on volatile indicators (GDP growth) because
         those rarely have multi-year gaps.
      2. Drop any series whose NaN rate exceeds MAX_MISSING_RATE after filling.
         A >40% gap in a 20-year window means fewer than 12 data points —
         insufficient for a meaningful trend line.

    Returns cleaned DataFrame and a stats dict for the printed cleaning log.
    """
    nan_before = long["Value"].isna().sum()

    long = long.sort_values(["Country Code", "Series Code", "Year"])

    long["Value"] = (
        long
        .groupby(["Country Code", "Series Code"])["Value"]
        .transform(lambda s: s.ffill(limit=MAX_GAP_FILL))
    )

    nan_after_fill = long["Value"].isna().sum()

    missing_rate = (
        long
        .groupby(["Country Code", "Series Code"])["Value"]
        .apply(lambda s: s.isna().mean())
        .reset_index(name="missing_rate")
    )

    drop_pairs = missing_rate[missing_rate["missing_rate"] > MAX_MISSING_RATE][
        ["Country Code", "Series Code"]
    ]

    long = long.merge(
        drop_pairs.assign(_drop=True),
        on=["Country Code", "Series Code"],
        how="left",
    )
    long = long[long["_drop"].isna()].drop(columns=["_drop"])

    stats = {
        "nan_before":     nan_before,
        "filled":         nan_before - nan_after_fill,
        "series_dropped": len(drop_pairs),
        "nan_final":      long["Value"].isna().sum(),
    }
    return long, stats


# ---------------------------------------------------------------------------
# Merge helper — combine two wide-format DataFrames, deduplicating by coverage
# ---------------------------------------------------------------------------
def merge_wide_sources(
    frames: list[pd.DataFrame],
    year_cols: list[str],
    country_filter: str | None = None,
) -> pd.DataFrame:
    """
    Concatenate multiple wide-format WDI DataFrames and deduplicate.

    When the same (Country Code, Series Code) appears in more than one source
    file, keep the row that has more non-null year values — this ensures that
    a newer download with more coverage wins over an older sparse one.

    Parameters
    ----------
    frames         : list of wide DataFrames (same schema)
    year_cols      : list of year column names present across all frames
    country_filter : if provided, keep only rows for this Country Code
    """
    combined = pd.concat(frames, ignore_index=True)

    if country_filter:
        combined = combined[combined["Country Code"] == country_filter].copy()

    # Remove WDI footer rows that have blank or descriptive Country Codes
    combined = combined[
        combined["Country Code"].notna() &
        combined["Country Code"].str.match(r"^[A-Z]{3}$")  # valid ISO-3 codes only
    ].copy()

    # Count populated year cells per row to decide which duplicate to keep
    combined["_coverage"] = combined[year_cols].apply(
        lambda row: (row != MISSING_SENTINEL) & row.notna(),
        axis=1
    ).sum(axis=1)

    combined = (
        combined
        .sort_values("_coverage", ascending=False)
        .drop_duplicates(subset=["Country Code", "Series Code"])
        .drop(columns=["_coverage"])
        .reset_index(drop=True)
    )
    return combined


# ---------------------------------------------------------------------------
# Core pipeline — reused for both Uzbekistan and regional files
# ---------------------------------------------------------------------------
def run_single_pipeline(
    raw: pd.DataFrame,
    label: str,
    out_path: Path,
) -> pd.DataFrame:
    year_cols = [c for c in raw.columns if "YR" in c]

    print()
    step1_explore(raw, year_cols, label)

    df = step2b_fix_types(raw.copy(), year_cols)
    long = step3_reshape(df, year_cols)
    print(f"    After melt   : {len(long):,} rows")

    long, stats = step2a_handle_missing(long)

    print(f"    NaN filled   : {stats['filled']:,}")
    print(f"    Series drop  : {stats['series_dropped']} (>{MAX_MISSING_RATE*100:.0f}% missing)")
    print(f"    NaN remain   : {stats['nan_final']:,}")
    print(f"    Final shape  : {long.shape}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    long.to_csv(out_path, index=False, encoding="utf-8")
    print(f"    Saved -> {out_path}")

    return long


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_pipeline() -> None:
    print("=" * 60)
    print("WDI CLEANING PIPELINE")
    print("=" * 60)

    # ── Uzbekistan: merge both source files ──────────────────────────────
    existing = [p for p in UZB_SOURCES if p.exists()]
    if not existing:
        raise FileNotFoundError(f"No source files found in {ORIG}")

    print(f"\nLoading {len(existing)} Uzbekistan source file(s):")
    frames = []
    all_year_cols: list[str] = []
    for p in existing:
        df = pd.read_csv(p, encoding="utf-8", dtype=str)
        year_cols = [c for c in df.columns if "YR" in c]
        all_year_cols = year_cols  # same across WDI exports
        print(f"  {p.name}  ({len(df)} rows)")
        frames.append(df)

    uzb_wide = merge_wide_sources(frames, all_year_cols, country_filter="UZB")
    print(f"\nAfter merge+dedup: {len(uzb_wide)} unique Uzbekistan series")

    run_single_pipeline(uzb_wide, "uzbekistan_merged", UZB_OUT)

    # ── Regional: only if the file exists ───────────────────────────────
    if REG_SOURCE.exists():
        reg_raw = pd.read_csv(REG_SOURCE, encoding="utf-8", dtype=str)
        print("\nRegional file found — cleaning comparison data")
        run_single_pipeline(reg_raw, "central_asia", REG_OUT)
    else:
        print(f"\n[SKIP] Regional file not yet downloaded: {REG_SOURCE.name}")
        print("       Radar and Choropleth will show placeholder until it arrives.")

    print("\nDone.")


if __name__ == "__main__":
    run_pipeline()
