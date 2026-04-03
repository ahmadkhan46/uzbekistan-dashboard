# 🇺🇿 Uzbekistan Development Dashboard

An interactive data visualisation dashboard tracking Uzbekistan's development indicators from 2006 to 2025, built with Python and Dash.

**Live Demo:** [uzbekistan-dashboard.onrender.com](https://uzbekistan-dashboard.onrender.com)

---

## Visualisations

- **Spiral Chart** — GDP growth rate plotted as an Archimedean spiral, revealing cyclical patterns across two decades
- **Radar Plot** — 7-indicator development profile comparing Uzbekistan across time periods
- **Choropleth Map** — Geospatial view of Uzbekistan with year-selectable indicators

## Dashboard Features

- Year range selector (2006–2025) — all charts update simultaneously
- 5 KPI cards with decade-on-decade delta indicators
- 6 trend sparklines (GDP growth, GDP per capita, life expectancy, infant mortality, electricity access, CO₂)
- Dark theme with responsive layout

## Data Source

All data sourced exclusively from the [World Bank WDI](https://databank.worldbank.org/source/world-development-indicators).

| Indicator | Code |
|-----------|------|
| GDP Growth (annual %) | NY.GDP.MKTP.KD.ZG |
| GDP per Capita (US$) | NY.GDP.PCAP.CD |
| Life Expectancy | SP.DYN.LE00.IN |
| Infant Mortality | SP.DYN.IMRT.IN |
| Electricity Access (%) | EG.ELC.ACCS.ZS |
| CO₂ per Capita | EN.GHG.CO2.PC.CE.AR5 |
| Renewable Energy (%) | EG.FEC.RNEW.ZS |
| Secondary Enrolment (%) | SE.SEC.ENRR |

## Tech Stack

| Library | Version |
|---------|---------|
| Dash | 2.18.1 |
| Plotly | 5.24.1 |
| Pandas | 2.3.3 |
| NumPy | 2.2.3 |
| Dash Bootstrap Components | 1.6.0 |

## Run Locally

```bash
pip install -r requirements.txt
python dashboard/app.py
```

Then open [http://127.0.0.1:8050](http://127.0.0.1:8050)

## Data Pipeline

To regenerate the cleaned dataset from raw WDI exports:

```bash
python clean_data.py
```

Cleaning steps:
1. **Explore** — raw shape, null profile, year range
2. **Type coercion** — replace `..` sentinel → NaN, cast to float64
3. **Missing values** — forward-fill gaps ≤ 3 years, drop series > 40% missing
4. **Reshape** — wide format → long format (Year, Value columns)

---

*MSc Data Visualisation — Assignment 2*
