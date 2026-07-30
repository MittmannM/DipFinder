from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote
import json
import re
import time

import pandas as pd
import requests


BASE_URL = "https://markets.sh/api/v1"
CACHE_DIR = Path(".cache") / "markets_sh"
CACHE_TTL_SECONDS = 60 * 60
REQUEST_TIMEOUT_SECONDS = 30

YAHOO_EXCHANGE_TO_MARKETS_SH = {
    "ASE": "AMEX",
    "AMS": "AMS",
    "CPH": "CPH",
    "FRA": "FRA",
    "GER": "XETRA",
    "HEL": "HEL",
    "LSE": "LSE",
    "MCE": "BME",
    "MIL": "MIL",
    "NCM": "NASDAQ",
    "NGM": "NASDAQ",
    "NMS": "NASDAQ",
    "NAS": "NASDAQ",
    "NYQ": "NYSE",
    "OSL": "OSL",
    "PAR": "EPA",
    "STO": "STO",
    "SWX": "SWX",
    "TOR": "TSX",
    "VIE": "VIE",
}


class MarketsShError(RuntimeError):
    pass


def normalize_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def to_number(value):
    if isinstance(value, dict):
        for key in ("value", "raw", "amount"):
            if key in value:
                value = value[key]
                break

    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value) if pd.notna(value) else None

    text = str(value).strip()
    if text.lower() in ("", "-", "--", "n/a", "none", "null", "nan"):
        return None

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]

    multiplier = 1.0
    suffixes = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}
    suffix = text[-1:].lower()
    if suffix in suffixes:
        multiplier = suffixes[suffix]
        text = text[:-1]

    text = re.sub(r"[^0-9eE+.,-]", "", text).replace(",", "")
    try:
        number = float(text) * multiplier
    except ValueError:
        return None

    return -number if negative else number


def safe_divide(numerator, denominator):
    numerator = to_number(numerator)
    denominator = to_number(denominator)
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def cache_path(name):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    return CACHE_DIR / f"{safe_name}.json"


def request_json(path, api_token, params=None, cache_name=None, refresh=False):
    if not api_token:
        raise MarketsShError("MARKETS_SH_API_TOKEN is missing.")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path_on_disk = cache_path(cache_name) if cache_name else None

    if (
        path_on_disk
        and not refresh
        and path_on_disk.exists()
        and time.time() - path_on_disk.stat().st_mtime < CACHE_TTL_SECONDS
    ):
        return json.loads(path_on_disk.read_text(encoding="utf-8"))

    response = requests.get(
        f"{BASE_URL}/{path.lstrip('/')}",
        params=params,
        headers={"X-API-Key": api_token, "Accept": "application/json"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if response.status_code in (401, 403):
        raise MarketsShError("markets.sh rejected the API token.")
    if response.status_code == 429:
        raise MarketsShError("markets.sh rate limit reached. Cached tickers still work.")

    try:
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise MarketsShError(f"markets.sh request failed: {exc}") from exc

    if isinstance(payload, dict) and payload.get("error"):
        raise MarketsShError(str(payload["error"]))

    if path_on_disk:
        path_on_disk.write_text(json.dumps(payload), encoding="utf-8")

    return payload


def yahoo_quote(ticker, refresh=False):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path_on_disk = cache_path(f"yahoo_{ticker}")

    if (
        not refresh
        and path_on_disk.exists()
        and time.time() - path_on_disk.stat().st_mtime < CACHE_TTL_SECONDS
    ):
        return json.loads(path_on_disk.read_text(encoding="utf-8"))

    response = requests.get(
        "https://query2.finance.yahoo.com/v1/finance/search",
        params={"q": ticker, "quotesCount": 10, "newsCount": 0},
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    try:
        response.raise_for_status()
        quotes = response.json().get("quotes", [])
    except (requests.RequestException, ValueError) as exc:
        raise MarketsShError(f"Yahoo symbol lookup failed: {exc}") from exc

    ticker_upper = ticker.upper()
    match = next(
        (
            item
            for item in quotes
            if str(item.get("symbol", "")).upper() == ticker_upper
            and item.get("quoteType") in (None, "EQUITY")
        ),
        None,
    )
    if not match:
        raise MarketsShError(f"Yahoo returned no exact equity match for {ticker}.")

    path_on_disk.write_text(json.dumps(match), encoding="utf-8")
    return match


def extract_records(payload):
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("data", "results", "items", "financials", "records", "annualReports"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = extract_records(value)
            if nested:
                return nested

    for value in payload.values():
        nested = extract_records(value)
        if nested and any(record_year(record) is not None for record in nested):
            return nested

    dated_records = []
    for key, value in payload.items():
        if isinstance(value, dict) and re.search(r"(?:19|20)\d{2}", str(key)):
            record = dict(value)
            record.setdefault("date", key)
            dated_records.append(record)

    return dated_records


def all_dicts(payload):
    if isinstance(payload, dict):
        yield payload
        for value in payload.values():
            yield from all_dicts(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from all_dicts(value)


def record_value(record, candidates):
    normalized = {normalize_key(key): value for key, value in record.items()}
    for candidate in candidates:
        key = normalize_key(candidate)
        if key in normalized:
            return to_number(normalized[key])
    return None


def record_year(record):
    normalized = {normalize_key(key): value for key, value in record.items()}
    for candidate in ("calendarYear", "fiscalYear", "year", "date", "periodEndDate"):
        value = normalized.get(normalize_key(candidate))
        match = re.search(r"(?:19|20)\d{2}", str(value))
        if match:
            return int(match.group(0))
    return None


def records_to_series(records, candidates):
    result = {}
    for record in records:
        year = record_year(record)
        value = record_value(record, candidates)
        if year is not None and value is not None:
            result[year] = value
    return result


def combine_series(*series, operation):
    years = set().union(*(item.keys() for item in series))
    result = {}
    for year in years:
        value = operation(*(item.get(year) for item in series))
        if value is not None:
            result[year] = value
    return result


def fill_missing(primary, fallback):
    result = dict(primary)
    for year, value in fallback.items():
        if result.get(year) is None:
            result[year] = value
    return result


def yoy_growth(series, years):
    growth = [None]
    for previous_year, current_year in zip(years, years[1:]):
        previous = series.get(previous_year)
        current = series.get(current_year)
        value = (
            safe_divide(current - previous, abs(previous))
            if previous not in (None, 0) and current is not None
            else None
        )
        growth.append(value)
    return growth if years else []


def company_name_similarity(left, right):
    def clean(value):
        words = normalize_key(value)
        for suffix in ("incorporated", "corporation", "company", "limited", "inc", "corp", "ltd", "plc", "ag", "se"):
            if words.endswith(suffix):
                words = words[: -len(suffix)]
        return words

    left = clean(left)
    right = clean(right)
    if not left or not right:
        return 0
    return SequenceMatcher(None, left, right).ratio()


def markets_symbol_exists(symbol, api_token, refresh=False):
    try:
        payload = request_json(
            f"symbols/{quote(symbol, safe=':')}",
            api_token,
            cache_name=f"symbol_{symbol}",
            refresh=refresh,
        )
    except MarketsShError:
        return False

    expected = symbol.upper()
    expected_ticker = expected.split(":", 1)[-1]
    for item in all_dicts(payload):
        normalized = {normalize_key(key): value for key, value in item.items()}
        symbol_id = str(normalized.get("mshid") or normalized.get("id") or "").upper()
        result_ticker = str(normalized.get("symbol") or "").upper()
        if symbol_id == expected or (result_ticker == expected_ticker and expected.startswith(f"{symbol_id.split(':', 1)[0]}:")):
            return True

    return False


def resolve_symbol(ticker, api_token, refresh=False):
    ticker = ticker.strip()
    if ":" in ticker:
        return ticker.upper()

    yahoo = yahoo_quote(ticker, refresh=refresh)
    ticker_upper = ticker.upper()
    ticker_base = ticker_upper.split(".", 1)[0]
    yahoo_exchange = str(yahoo.get("exchange", "")).upper()
    expected_exchange = YAHOO_EXCHANGE_TO_MARKETS_SH.get(yahoo_exchange)
    company_name = yahoo.get("longname") or yahoo.get("shortname") or ""

    if expected_exchange:
        direct_symbol = f"{expected_exchange}:{ticker_base}"
        if markets_symbol_exists(direct_symbol, api_token, refresh=refresh):
            return direct_symbol

    best_match = None
    best_score = -1

    search_terms = [ticker]
    if company_name and normalize_key(company_name) != normalize_key(ticker):
        search_terms.append(company_name)

    for search_term in search_terms:
        payload = request_json(
            "symbols/search",
            api_token,
            params={"q": search_term, "query": search_term, "limit": 25},
            cache_name=f"search_{search_term}",
            refresh=refresh,
        )

        for item in all_dicts(payload):
            normalized = {normalize_key(key): value for key, value in item.items()}
            symbol_id = next(
                (
                    normalized.get(normalize_key(key))
                    for key in ("msh_id", "mshId", "id")
                    if normalized.get(normalize_key(key))
                ),
                None,
            )
            if not symbol_id or ":" not in str(symbol_id):
                continue

            source_ref = str(normalized.get("sourceref", "")).upper()
            result_symbol = str(normalized.get("symbol", "")).upper()
            result_name = str(normalized.get("name", ""))
            result_exchange = str(symbol_id).split(":", 1)[0].upper()
            name_similarity = company_name_similarity(company_name, result_name)
            exact_reference = source_ref == ticker_upper
            exact_symbol = result_symbol in (ticker_base, ticker_upper)
            matching_exchange = expected_exchange and result_exchange == expected_exchange

            if not exact_reference and not exact_symbol and name_similarity < 0.82:
                continue
            if exact_symbol and expected_exchange and not matching_exchange and name_similarity < 0.82:
                continue

            score = 0
            score += 200 if exact_reference else 0
            score += 100 if exact_symbol else 0
            score += 60 if matching_exchange else 0
            score += int(name_similarity * 50)
            score += 10 if normalized.get("isprimary") is True else 0

            if score > best_score:
                best_match = str(symbol_id)
                best_score = score

    if not best_match:
        expected = f" (expected {expected_exchange}:{ticker_base})" if expected_exchange else ""
        raise MarketsShError(f"No exact markets.sh company match found for {ticker}{expected}.")

    return best_match


def build_graph_data(income, balance, cashflow, key_metrics=None, years=10):
    key_metrics = key_metrics or []
    revenue = records_to_series(income, ["revenue", "totalRevenue"])
    operating_income = records_to_series(income, ["operatingIncome", "ebit"])
    pretax_income = records_to_series(income, ["incomeBeforeTax", "pretaxIncome"])
    income_tax = records_to_series(income, ["incomeTaxExpense", "taxProvision"])
    net_income = records_to_series(income, ["netIncome", "netIncomeCommonStockholders"])
    ebitda = records_to_series(income, ["ebitda"])
    eps_diluted = records_to_series(income, ["epsDiluted", "epsdiluted", "dilutedEPS"])
    shares = records_to_series(
        income,
        ["weightedAverageShsOutDil", "weightedAverageSharesDiluted", "dilutedAverageShares"],
    )
    pe_ratio = records_to_series(
        key_metrics,
        ["peRatio", "priceEarningsRatio", "priceToEarningsRatio"],
    )
    pfcf_ratio = records_to_series(
        key_metrics,
        ["pfcfRatio", "priceToFreeCashFlowsRatio", "priceToFreeCashFlowRatio"],
    )

    depreciation = records_to_series(
        cashflow,
        ["depreciationAndAmortization", "depreciationAmortizationDepletion"],
    )
    operating_cashflow = records_to_series(
        cashflow,
        ["operatingCashFlow", "netCashProvidedByOperatingActivities"],
    )
    capex = records_to_series(cashflow, ["capitalExpenditure", "capitalExpenditures"])
    free_cashflow = records_to_series(cashflow, ["freeCashFlow"])
    free_cashflow = fill_missing(
        free_cashflow,
        combine_series(
            operating_cashflow,
            capex,
            operation=lambda cfo, spending: cfo + spending
            if cfo is not None and spending is not None
            else None,
        ),
    )
    dividends = records_to_series(
        cashflow,
        ["dividendsPaid", "commonDividendsPaid", "cashDividendsPaid"],
    )
    dividends = {year: abs(value) for year, value in dividends.items()}

    cash = records_to_series(
        balance,
        ["cashAndCashEquivalents", "cashAndCashEquivalentsAtCarryingValue"],
    )
    short_investments = records_to_series(balance, ["shortTermInvestments"])
    total_debt = records_to_series(balance, ["totalDebt"])
    net_debt = records_to_series(balance, ["netDebt"])
    net_debt = fill_missing(
        net_debt,
        combine_series(
            total_debt,
            cash,
            short_investments,
            operation=lambda debt, cash_value, investments: debt - cash_value - (investments or 0)
            if debt is not None and cash_value is not None
            else None,
        ),
    )
    equity = records_to_series(
        balance,
        ["totalStockholdersEquity", "stockholdersEquity", "totalEquity"],
    )
    total_assets = records_to_series(balance, ["totalAssets"])
    current_liabilities = records_to_series(
        balance,
        ["totalCurrentLiabilities", "currentLiabilities"],
    )

    ebitda = fill_missing(
        ebitda,
        combine_series(
            operating_income,
            depreciation,
            operation=lambda operating, da: operating + da
            if operating is not None and da is not None
            else None,
        ),
    )
    eps_diluted = fill_missing(
        eps_diluted,
        combine_series(
            net_income,
            shares,
            operation=lambda income_value, share_count: safe_divide(income_value, share_count),
        ),
    )
    dividends_per_share = combine_series(
        dividends,
        shares,
        operation=lambda paid, share_count: safe_divide(paid, share_count),
    )

    tax_rate = combine_series(
        income_tax,
        pretax_income,
        operation=lambda tax, pretax: min(max(tax / pretax, 0), 0.35)
        if tax is not None and pretax not in (None, 0)
        else 0.21,
    )
    nopat = combine_series(
        operating_income,
        tax_rate,
        operation=lambda operating, rate: operating * (1 - rate)
        if operating is not None and rate is not None
        else None,
    )
    invested_capital = combine_series(
        total_debt,
        equity,
        cash,
        short_investments,
        operation=lambda debt, equity_value, cash_value, investments: (
            debt + equity_value - cash_value - (investments or 0)
        )
        if debt is not None and equity_value is not None and cash_value is not None
        else None,
    )
    capital_employed = combine_series(
        total_assets,
        current_liabilities,
        operation=lambda assets, liabilities: assets - liabilities
        if assets is not None and liabilities is not None
        else None,
    )
    roic = combine_series(
        nopat,
        invested_capital,
        operation=lambda profit, capital: safe_divide(profit, capital) * 100
        if safe_divide(profit, capital) is not None
        else None,
    )
    roce = combine_series(
        operating_income,
        capital_employed,
        operation=lambda operating, capital: safe_divide(operating, capital) * 100
        if safe_divide(operating, capital) is not None
        else None,
    )

    available_years = sorted(revenue)[-years:]
    if not available_years:
        raise MarketsShError("markets.sh returned no annual revenue data.")

    return pd.DataFrame(
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
            "Dividends PS Growth": yoy_growth(dividends_per_share, available_years),
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


def get_annual_fundamentals(ticker, api_token, years=10, refresh=False):
    symbol = resolve_symbol(ticker, api_token, refresh=refresh)
    encoded_symbol = quote(symbol, safe=":")
    end_date = date.today()
    start_date = date(end_date.year - years - 1, 1, 1)
    params = {"period": "FY", "from": start_date.isoformat(), "to": end_date.isoformat()}

    statements = {}
    for statement in ("income_statement", "balance_sheet", "cash_flow"):
        payload = request_json(
            f"symbols/{encoded_symbol}/financials/{statement}",
            api_token,
            params=params,
            cache_name=f"{symbol}_{statement}_{start_date.year}_{end_date.year}",
            refresh=refresh,
        )
        records = extract_records(payload)
        if not records:
            raise MarketsShError(f"markets.sh returned no {statement} records for {symbol}.")
        statements[statement] = records

    try:
        metrics_payload = request_json(
            f"symbols/{encoded_symbol}/financials/key_metrics",
            api_token,
            params=params,
            cache_name=f"{symbol}_key_metrics_{start_date.year}_{end_date.year}",
            refresh=refresh,
        )
        key_metrics = extract_records(metrics_payload)
    except MarketsShError:
        # Valuation history is optional; statement charts should still load if
        # this endpoint is unavailable for a symbol or plan.
        key_metrics = []

    frame = build_graph_data(
        statements["income_statement"],
        statements["balance_sheet"],
        statements["cash_flow"],
        key_metrics=key_metrics,
        years=years,
    )
    frame.attrs["source"] = "markets.sh"
    frame.attrs["source_symbol"] = symbol
    return frame
