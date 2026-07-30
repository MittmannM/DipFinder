from io import StringIO
from pathlib import Path
import re
import time

import pandas as pd
import requests


BASE_URL = "https://stockanalysis.com"
CACHE_DIR = Path(".cache") / "stockanalysis"
CACHE_TTL_SECONDS = 60 * 60
REQUEST_DELAY_SECONDS = 1.0
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DipFinder/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

YAHOO_SUFFIX_TO_STOCKANALYSIS_EXCHANGE = {
    "AS": "ams",
    "CO": "cph",
    "DE": "etr",
    "F": "fra",
    "L": "lon",
    "MI": "bit",
    "MC": "bme",
    "PA": "epa",
    "ST": "sto",
    "SW": "swx",
    "TO": "tsx",
    "VI": "vie",
}


def to_number(value):
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()
    if text in ("", "-", "--", "n/a", "N/A", "None", "nan"):
        return None

    multiplier = 1
    if text.endswith("%"):
        text = text[:-1]
    if text.startswith("(") and text.endswith(")"):
        multiplier = -1
        text = text[1:-1]

    text = text.replace("$", "").replace("€", "").replace("£", "")
    text = text.replace(",", "").replace("\u2212", "-").strip()

    try:
        return float(text) * multiplier
    except ValueError:
        return None


def safe_divide(numerator, denominator):
    numerator = to_number(numerator)
    denominator = to_number(denominator)

    if numerator is None or denominator in (None, 0):
        return None

    return numerator / denominator


def normalize_label(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def year_from_column(column):
    match = re.search(r"(?:FY\s*)?((?:19|20)\d{2})", str(column))
    return int(match.group(1)) if match else None


def cache_path(url):
    slug = url.replace(BASE_URL, "").strip("/").replace("/", "__")
    return CACHE_DIR / f"{slug or 'home'}.html"


def fetch_html(url, refresh=False):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(url)

    if not refresh and path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL_SECONDS:
        return path.read_text(encoding="utf-8")

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    html = response.text
    path.write_text(html, encoding="utf-8")
    time.sleep(REQUEST_DELAY_SECONDS)

    return html


def ticker_url_candidates(ticker):
    raw = ticker.strip()

    if ":" in raw:
        exchange, symbol = raw.split(":", 1)
        return [f"{BASE_URL}/quote/{exchange.lower()}/{symbol.upper()}"]

    if "." in raw:
        symbol, suffix = raw.rsplit(".", 1)
        exchange = YAHOO_SUFFIX_TO_STOCKANALYSIS_EXCHANGE.get(suffix.upper())
        candidates = []

        if exchange:
            candidates.append(f"{BASE_URL}/quote/{exchange}/{symbol.upper()}")

        candidates.append(f"{BASE_URL}/stocks/{symbol.lower()}")
        return candidates

    return [f"{BASE_URL}/stocks/{raw.lower()}"]


def page_urls(ticker):
    for base in ticker_url_candidates(ticker):
        yield "income", f"{base}/financials/income-statement/"
        yield "balance", f"{base}/financials/balance-sheet/"
        yield "cashflow", f"{base}/financials/cash-flow-statement/"
        yield "ratios", f"{base}/financials/ratios/"


def flatten_columns(table):
    table = table.copy()

    if isinstance(table.columns, pd.MultiIndex):
        table.columns = [
            next((str(part) for part in column if str(part) and not str(part).startswith("Unnamed")), "")
            for column in table.columns
        ]
    else:
        table.columns = [str(column) for column in table.columns]

    return table


def html_to_series_map(html):
    tables = pd.read_html(StringIO(html))
    series_map = {}

    for table in tables:
        table = flatten_columns(table)
        first_col = str(table.columns[0])
        if "Fiscal Year" in table.columns or "Fiscal Year" in first_col:
            table = table.rename(columns={table.columns[0]: "Metric"})
            series_map.update(statement_to_series(table))

    if not series_map:
        raise ValueError("No financial table found on page.")

    return series_map


def statement_to_series(statement):
    year_columns = {column: year_from_column(column) for column in statement.columns}
    year_columns = {column: year for column, year in year_columns.items() if year is not None}
    series = {}

    for _, row in statement.iterrows():
        metric = str(row["Metric"]).strip()
        if not metric or metric == "Period Ending":
            continue

        values = {}
        for column, year in year_columns.items():
            value = to_number(row[column])
            if value is not None:
                values[year] = value

        if values:
            series[metric] = values

    return series


def find_series(series_map, candidates):
    normalized = {normalize_label(key): value for key, value in series_map.items()}

    for candidate in candidates:
        candidate = normalize_label(candidate)

        if candidate in normalized:
            return normalized[candidate]

    for candidate in candidates:
        candidate = normalize_label(candidate)

        for label, values in normalized.items():
            if candidate in label:
                return values

    return {}


def combine_series(*series, operation):
    years = set().union(*(item.keys() for item in series))
    combined = {}

    for year in years:
        result = operation(*(item.get(year) for item in series))
        if result is not None:
            combined[year] = result

    return combined


def yoy_growth(series, years):
    if not years:
        return []

    growth = []

    for previous_year, current_year in zip(years, years[1:]):
        previous_value = series.get(previous_year)
        current_value = series.get(current_year)
        growth_value = (
            safe_divide(current_value - previous_value, abs(previous_value))
            if previous_value not in (None, 0) and current_value is not None
            else None
        )
        growth.append(growth_value)

    return [None] + growth


def load_statement_pages(ticker, refresh=False):
    last_error = None
    found_any = False

    for page_name, url in page_urls(ticker):
        try:
            html = fetch_html(url, refresh=refresh)
            series_map = html_to_series_map(html)
            found_any = True
            yield page_name, series_map
        except Exception as exc:
            last_error = exc
            continue

    if found_any:
        return

    if last_error is not None:
        raise ValueError(f"No readable StockAnalysis pages found for ticker {ticker}: {last_error}")

    raise ValueError(f"No StockAnalysis pages found for ticker {ticker}.")


def get_annual_fundamentals(ticker, years=10, refresh=False):
    pages = dict(load_statement_pages(ticker, refresh=refresh))

    income = pages.get("income", {})
    balance = pages.get("balance", {})
    cashflow = pages.get("cashflow", {})
    ratios = pages.get("ratios", {})

    revenue = find_series(income, ["Revenue"])
    free_cashflow = find_series(cashflow, ["Free Cash Flow"])
    net_debt = find_series(balance, ["Net Debt"])
    if not net_debt:
        net_cash = find_series(balance, ["Net Cash Debt", "Net Cash"])
        net_debt = {year: -value for year, value in net_cash.items()}
    eps_diluted = find_series(income, ["EPS Diluted", "Earnings Per Share", "EPS"])
    dividends = find_series(cashflow, ["Dividends Paid", "Cash Dividends Paid", "Common Dividends Paid"])
    dividends = {year: abs(value) for year, value in dividends.items()}
    net_income = find_series(income, ["Net Income"])
    ebitda = find_series(income, ["EBITDA"])
    shares = find_series(
        income,
        [
            "Shares Outstanding Diluted",
            "Shares Outstanding Basic",
            "Diluted Shares Outstanding",
            "Basic Shares Outstanding",
            "Shares Outstanding",
        ],
    )
    roic = find_series(ratios, ["Return on Invested Capital ROIC", "ROIC"])
    roce = find_series(ratios, ["Return on Capital Employed ROCE", "ROCE"])
    pe_ratio = find_series(ratios, ["PE Ratio", "P/E Ratio"])
    pfcf_ratio = find_series(ratios, ["P/FCF Ratio", "Price to Free Cash Flow"])
    dividend_per_share = find_series(income, ["Dividends Per Share", "Dividend Per Share"])
    dividend_per_share = dividend_per_share or find_series(ratios, ["Dividends Per Share", "Dividend Per Share"])

    if not dividends and dividend_per_share and shares:
        dividends = combine_series(
            dividend_per_share,
            shares,
            operation=lambda dividend, share_count: dividend * share_count
            if dividend is not None and share_count is not None
            else None,
        )

    available_years = sorted(set(revenue.keys()))[-years:]

    if not available_years:
        raise ValueError(f"No annual revenue data found for ticker {ticker}.")

    frame = pd.DataFrame(
        {
            "Date": available_years,
            "Revenue": [revenue.get(year) for year in available_years],
            "Revenue Growth": yoy_growth(revenue, available_years),
            "Free Cash Flow": [free_cashflow.get(year) for year in available_years],
            "Free Cash Flow Growth": yoy_growth(free_cashflow, available_years),
            "Net Debt": [net_debt.get(year) for year in available_years],
            "EPS Diluted": [eps_diluted.get(year) for year in available_years],
            "EPS Diluted Growth": yoy_growth(eps_diluted, available_years),
            "PE Ratio": [pe_ratio.get(year) for year in available_years],
            "P/FCF Ratio": [pfcf_ratio.get(year) for year in available_years],
            "Dividends": [dividends.get(year) for year in available_years],
            "Dividends PS Growth": yoy_growth(dividend_per_share, available_years),
            "Net Income": [net_income.get(year) for year in available_years],
            "Net Income Growth": yoy_growth(net_income, available_years),
            "EBITDA": [ebitda.get(year) for year in available_years],
            "EBITDA Growth": yoy_growth(ebitda, available_years),
            "Shares Outstanding": [shares.get(year) for year in available_years],
            "Shares Outstanding Growth": yoy_growth(shares, available_years),
            "ROCE": [roce.get(year) for year in available_years],
            "ROIC": [roic.get(year) for year in available_years],
        }
    )
    frame.attrs["source"] = "StockAnalysis"
    frame.attrs["source_symbol"] = ticker.upper()
    return frame
