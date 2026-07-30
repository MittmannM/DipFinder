# DipFinder

Personal Streamlit dashboard for stock valuation and fundamental analysis.

The app contains three views:

- `Analysis` for current valuation and annual fundamental charts
- `Watchlist` with the multi-stock Dip Finder
- `DCF Calculator` for five-year earnings and cash-flow projections

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Fundamental data

The app uses the free markets.sh API for annual income statements, balance sheets
cash-flow statements and historical valuation metrics. Create a free account at
https://markets.sh and set the API token before starting the app:

```powershell
$env:MARKETS_SH_API_TOKEN="your-token"
streamlit run app.py
```

The app loads up to 20 annual periods once and slices that shared history for the
selected view. Provider responses and repository results are cached for one hour.
All views access external data through `repositories/stock_data_repository.py`, so cached ticker
information, prices and fundamentals can be reused across Analysis, Watchlist and
DCF Calculator. Growth rates, net debt, ROIC and ROCE are calculated locally.

Yahoo Finance remains the source for prices and current valuation figures.

## Project structure

- `app.py` contains only app configuration and view navigation.
- `ui/` contains Streamlit views; every module name ends in `_ui.py`.
- `services/` contains API-free calculations; every module name ends in `_service.py`.
- `providers/` contains external data integrations; every module name ends in `_provider.py`.
- `repositories/` coordinates providers, persistence and the shared one-hour cache; every module name ends in `_repository.py`.

## Watchlist Dip Finder

The Watchlist tab validates ticker symbols through Yahoo Finance and stores the
company name locally in `watchlist.json`. Its Dip Finder compares all watchlist
stocks across selectable periods from one week to one year.

The repository loads 20 years of daily adjusted closes once. Price returns and
52-week metrics select only the observations required for each calculation.
Historical P/E values come from Yahoo's annual valuation history. Historical
P/FCF is calculated from Yahoo's period-end market capitalisation and the free
cash flow reported for the same fiscal year. Invalid or negative multiples are
excluded from percentile calculations.

## DCF Calculator

The calculator loads the current price, TTM earnings, P/E, free cash flow and
available growth data from Yahoo Finance. User assumptions control the five-year
growth rate, terminal P/E or FCF yield, and desired annual return. Dividends are
not included in the projection.

Run the service tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
