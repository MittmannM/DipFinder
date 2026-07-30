from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


YFINANCE_CACHE_PATH = Path(__file__).resolve().parents[1] / ".yfinance-cache"
YFINANCE_CACHE_PATH.mkdir(exist_ok=True)
yf.set_tz_cache_location(str(YFINANCE_CACHE_PATH))


def _number(value):
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_divide(numerator, denominator):
    numerator = _number(numerator)
    denominator = _number(denominator)
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _positive_number(value):
    number = _number(value)
    if number is None or not np.isfinite(number) or number <= 0:
        return None
    return number


def _combine_series(*series, operation):
    years = set().union(*(item.keys() for item in series))
    result = {}
    for year in years:
        value = operation(*(item.get(year) for item in series))
        if value is not None:
            result[year] = value
    return result


def _yoy_growth(series, years):
    growth = [None]
    for previous_year, current_year in zip(years, years[1:]):
        previous = series.get(previous_year)
        current = series.get(current_year)
        value = (
            _safe_divide(current - previous, abs(previous))
            if previous not in (None, 0) and current is not None
            else None
        )
        growth.append(value)
    return growth if years else []


def _clean_statement(statement):
    if statement is None or statement.empty:
        return pd.DataFrame()
    cleaned = statement.copy()
    cleaned.columns = pd.to_datetime(cleaned.columns).year
    cleaned = cleaned.loc[:, ~cleaned.columns.duplicated()]
    return cleaned.sort_index(axis=1)


def _get_statement(ticker_object, method_name, attribute_name):
    try:
        statement = getattr(ticker_object, method_name)(pretty=True, freq="yearly")
    except Exception:
        statement = getattr(ticker_object, attribute_name, pd.DataFrame())
    return _clean_statement(statement)


def _statement_series(statement, rows):
    for row in rows:
        if row in statement.index:
            return {
                int(year): _number(value)
                for year, value in statement.loc[row].items()
                if _number(value) is not None
            }
    return {}


def _fill_missing(primary, fallback):
    result = dict(primary)
    for year, value in fallback.items():
        if result.get(year) is None:
            result[year] = value
    return result


def _annual_shares(ticker_object, start_year, end_year):
    try:
        shares = ticker_object.get_shares_full(
            start=f"{start_year}-01-01",
            end=f"{end_year + 1}-01-01",
        )
    except Exception:
        return {}
    if shares is None or shares.empty:
        return {}
    shares.index = pd.to_datetime(shares.index)
    annual = shares.groupby(shares.index.year).last()
    return {
        int(year): _number(value)
        for year, value in annual.items()
        if _number(value) is not None
    }


def _annual_dividends_per_share(ticker_object):
    try:
        dividends = ticker_object.dividends
    except Exception:
        return {}
    if dividends is None or dividends.empty:
        return {}
    dividends.index = pd.to_datetime(dividends.index)
    annual = dividends.groupby(dividends.index.year).sum()
    return {
        int(year): _number(value)
        for year, value in annual.items()
        if _number(value) is not None
    }


def get_annual_fundamentals(ticker, years=20):
    symbol = str(ticker).strip().upper()
    if not symbol:
        raise ValueError("Ticker must not be empty.")

    ticker_object = yf.Ticker(symbol)
    income = _get_statement(ticker_object, "get_income_stmt", "income_stmt")
    cashflow = _get_statement(ticker_object, "get_cashflow", "cashflow")
    balance = _get_statement(ticker_object, "get_balance_sheet", "balance_sheet")

    revenue = _statement_series(income, ["Total Revenue", "Operating Revenue"])
    operating_cashflow = _statement_series(
        cashflow,
        ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    )
    capex = _statement_series(cashflow, ["Capital Expenditure", "Capital Expenditures"])
    free_cashflow = _statement_series(cashflow, ["Free Cash Flow"])
    free_cashflow = _fill_missing(
        free_cashflow,
        _combine_series(
            operating_cashflow,
            capex,
            operation=lambda cfo, spending: cfo + spending
            if cfo is not None and spending is not None
            else None,
        ),
    )

    cash = _statement_series(
        balance,
        [
            "Cash And Cash Equivalents",
            "Cash Cash Equivalents And Short Term Investments",
            "Cash Cash Equivalents Restricted Cash And Restricted Cash Equivalents",
        ],
    )
    total_debt = _statement_series(balance, ["Total Debt", "Net Debt"])
    net_debt = _statement_series(balance, ["Net Debt"])
    net_debt = _fill_missing(
        net_debt,
        _combine_series(
            total_debt,
            cash,
            operation=lambda debt, cash_value: debt - cash_value
            if debt is not None and cash_value is not None
            else None,
        ),
    )

    eps = _statement_series(
        income,
        ["Diluted EPS", "Diluted Eps", "Basic EPS", "Basic Eps"],
    )
    net_income = _statement_series(
        income,
        ["Net Income", "Net Income Common Stockholders"],
    )
    operating_income = _statement_series(income, ["Operating Income"])
    pretax_income = _statement_series(income, ["Pretax Income", "Income Before Tax"])
    income_tax = _statement_series(income, ["Tax Provision", "Income Tax Expense"])
    depreciation = _statement_series(
        cashflow,
        ["Depreciation And Amortization", "Depreciation Amortization Depletion"],
    )
    ebitda = _statement_series(income, ["EBITDA", "Normalized EBITDA"])
    ebitda = _fill_missing(
        ebitda,
        _combine_series(
            operating_income,
            depreciation,
            operation=lambda operating, da: operating + da
            if operating is not None and da is not None
            else None,
        ),
    )
    shares = _statement_series(
        income,
        ["Diluted Average Shares", "Basic Average Shares", "Weighted Average Shares Diluted"],
    )

    available_years = sorted(revenue)[-years:]
    if not available_years:
        raise ValueError(f"Yahoo Finance returned no annual revenue data for {symbol}.")

    shares = _fill_missing(
        shares,
        _annual_shares(ticker_object, min(available_years), max(available_years)),
    )
    eps = _fill_missing(
        eps,
        _combine_series(
            net_income,
            shares,
            operation=lambda income_value, share_count: _safe_divide(
                income_value,
                share_count,
            ),
        ),
    )

    dividends_per_share = _annual_dividends_per_share(ticker_object)
    dividends = _combine_series(
        dividends_per_share,
        shares,
        operation=lambda dividend, share_count: dividend * share_count
        if dividend is not None and share_count is not None
        else None,
    )

    equity = _statement_series(
        balance,
        ["Stockholders Equity", "Total Equity Gross Minority Interest"],
    )
    total_assets = _statement_series(balance, ["Total Assets"])
    current_liabilities = _statement_series(
        balance,
        ["Current Liabilities", "Total Current Liabilities"],
    )
    tax_rate = _combine_series(
        income_tax,
        pretax_income,
        operation=lambda tax, pretax: min(max(tax / pretax, 0), 0.35)
        if tax is not None and pretax not in (None, 0)
        else 0.21,
    )
    nopat = _combine_series(
        operating_income,
        tax_rate,
        operation=lambda operating, rate: operating * (1 - rate)
        if operating is not None and rate is not None
        else None,
    )
    invested_capital = _combine_series(
        total_debt,
        equity,
        cash,
        operation=lambda debt, equity_value, cash_value: debt + equity_value - cash_value
        if debt is not None and equity_value is not None and cash_value is not None
        else None,
    )
    capital_employed = _combine_series(
        total_assets,
        current_liabilities,
        operation=lambda assets, liabilities: assets - liabilities
        if assets is not None and liabilities is not None
        else None,
    )
    roic = _combine_series(
        nopat,
        invested_capital,
        operation=lambda profit, capital: _safe_divide(profit, capital) * 100
        if _safe_divide(profit, capital) is not None
        else None,
    )
    roce = _combine_series(
        operating_income,
        capital_employed,
        operation=lambda operating, capital: _safe_divide(operating, capital) * 100
        if _safe_divide(operating, capital) is not None
        else None,
    )

    frame = pd.DataFrame(
        {
            "Date": available_years,
            "Revenue": [revenue.get(year) for year in available_years],
            "Revenue Growth": _yoy_growth(revenue, available_years),
            "Free Cash Flow": [free_cashflow.get(year) for year in available_years],
            "Free Cash Flow Growth": _yoy_growth(free_cashflow, available_years),
            "Net Debt": [net_debt.get(year) for year in available_years],
            "EPS Diluted": [eps.get(year) for year in available_years],
            "EPS Diluted Growth": _yoy_growth(eps, available_years),
            "PE Ratio": [None for _ in available_years],
            "P/FCF Ratio": [None for _ in available_years],
            "Dividends": [dividends.get(year) for year in available_years],
            "Dividends PS Growth": _yoy_growth(dividends_per_share, available_years),
            "Net Income": [net_income.get(year) for year in available_years],
            "Net Income Growth": _yoy_growth(net_income, available_years),
            "EBITDA": [ebitda.get(year) for year in available_years],
            "EBITDA Growth": _yoy_growth(ebitda, available_years),
            "Shares Outstanding": [shares.get(year) for year in available_years],
            "Shares Outstanding Growth": _yoy_growth(shares, available_years),
            "ROCE": [roce.get(year) for year in available_years],
            "ROIC": [roic.get(year) for year in available_years],
        }
    )
    frame.attrs["source"] = "Yahoo Finance"
    frame.attrs["source_symbol"] = symbol
    return frame


def get_ticker_info(ticker):
    symbol = str(ticker).strip().upper()
    info = yf.Ticker(symbol).get_info()
    return info if isinstance(info, dict) else {}


def get_dividend_calendar(ticker):
    symbol = str(ticker).strip().upper()
    calendar = yf.Ticker(symbol).calendar
    return calendar if isinstance(calendar, dict) else {}


def get_annual_cashflow(ticker, pretty=True):
    symbol = str(ticker).strip().upper()
    try:
        return yf.Ticker(symbol).get_cash_flow(freq="yearly", pretty=pretty)
    except Exception:
        return pd.DataFrame()


def get_analyst_eps_growth(ticker):
    symbol = str(ticker).strip().upper()
    try:
        estimates = yf.Ticker(symbol).get_growth_estimates()
        if "+1y" in estimates.index and "stockTrend" in estimates.columns:
            growth = _number(estimates.at["+1y", "stockTrend"])
            if growth is not None:
                return growth, "Yahoo analyst estimate (+1Y)"
    except Exception:
        pass
    return None, None


def get_trailing_free_cash_flow(ticker):
    symbol = str(ticker).strip().upper()
    try:
        cashflow = yf.Ticker(symbol).get_cash_flow(freq="trailing", pretty=False)
    except Exception:
        return None
    if cashflow is None or cashflow.empty:
        return None
    for row_name in ("FreeCashFlow", "Free Cash Flow"):
        if row_name not in cashflow.index:
            continue
        values = pd.to_numeric(cashflow.loc[row_name], errors="coerce").dropna()
        if not values.empty:
            return _number(values.iloc[0])
    return None


def _single_level_columns(data):
    if not isinstance(data.columns, pd.MultiIndex):
        return data
    flattened = data.copy()
    flattened.columns = flattened.columns.get_level_values(0)
    return flattened


def _normalize_price_frame(data, price_column):
    if data is None or data.empty or price_column not in data.columns:
        return pd.DataFrame(columns=["Adjusted Close"])
    prices = pd.to_numeric(data[price_column], errors="coerce").dropna()
    if prices.empty:
        return pd.DataFrame(columns=["Adjusted Close"])
    prices.index = pd.to_datetime(prices.index, utc=True).tz_convert(None)
    prices = prices[~prices.index.duplicated(keep="last")].sort_index()
    return prices.rename("Adjusted Close").to_frame()


def get_price_history(ticker, years=20):
    symbol = str(ticker).strip().upper()
    if not isinstance(years, int) or years <= 0:
        raise ValueError("Years must be a positive integer.")

    end_date = pd.Timestamp.now().tz_localize(None).normalize() + pd.Timedelta(days=1)
    start_date = end_date - pd.DateOffset(years=years)
    download_error = None
    try:
        data = yf.download(
            symbol,
            start=start_date,
            end=end_date,
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
            multi_level_index=False,
        )
        result = _normalize_price_frame(_single_level_columns(data), "Adj Close")
        if not result.empty:
            return result
    except Exception as exc:
        download_error = exc

    try:
        data = yf.Ticker(symbol).history(
            start=start_date,
            end=end_date,
            interval="1d",
            auto_adjust=True,
            actions=False,
        )
        result = _normalize_price_frame(data, "Close")
        if not result.empty:
            return result
    except Exception as exc:
        if download_error is None:
            download_error = exc

    if download_error is not None:
        raise RuntimeError(f"Could not load adjusted price history for {symbol}: {download_error}")
    raise RuntimeError(f"Yahoo Finance returned no adjusted price history for {symbol}.")


def _valuation_row(frame, row_name):
    if frame is None or frame.empty or row_name not in frame.index:
        return None, {}
    current = _positive_number(frame.at[row_name, "Current"]) if "Current" in frame.columns else None
    history = {}
    for column, value in frame.loc[row_name].items():
        if column == "Current":
            continue
        number = _positive_number(value)
        if number is None:
            continue
        try:
            history[pd.Timestamp(column).normalize()] = number
        except (TypeError, ValueError):
            continue
    return current, history


def _dated_row_values(frame, row_names):
    if frame is None or frame.empty:
        return {}
    for row_name in row_names:
        if row_name not in frame.index:
            continue
        values = {}
        for column, value in frame.loc[row_name].items():
            number = _positive_number(value)
            if number is None:
                continue
            try:
                values[pd.Timestamp(column).normalize()] = number
            except (TypeError, ValueError):
                continue
        return values
    return {}


def _nearest_value(values, target_date, tolerance_days=45):
    if not values:
        return None
    nearest_date = min(values, key=lambda date: abs((date - target_date).days))
    if abs((nearest_date - target_date).days) > tolerance_days:
        return None
    return values[nearest_date]


def _history_series(values, name):
    cutoff = pd.Timestamp.now().tz_localize(None).normalize() - pd.DateOffset(years=5)
    filtered = {date: value for date, value in values.items() if date >= cutoff}
    if not filtered:
        return pd.Series(dtype="float64", name=name)
    series = pd.Series(filtered, dtype="float64", name=name).sort_index()
    series.index.name = "Date"
    return series


def get_valuation_history(ticker, ticker_info=None):
    symbol = str(ticker).strip().upper()
    ticker_object = yf.Ticker(symbol)
    try:
        valuations = ticker_object.get_valuation_measures(freq="yearly", periods=None)
    except Exception:
        valuations = pd.DataFrame()
    info = ticker_info if isinstance(ticker_info, dict) else get_ticker_info(symbol)

    current_pe, pe_history = _valuation_row(valuations, "Trailing P/E")
    current_market_cap, market_cap_history = _valuation_row(valuations, "Market Cap")
    current_pe = current_pe or _positive_number(info.get("trailingPE"))
    current_market_cap = current_market_cap or _positive_number(info.get("marketCap"))

    annual_cashflow = get_annual_cashflow(symbol, pretty=False)
    current_fcf = _positive_number(info.get("freeCashflow"))
    if current_fcf is None:
        current_fcf = _positive_number(get_trailing_free_cash_flow(symbol))
    if current_fcf is None:
        annual_values = _dated_row_values(annual_cashflow, ["FreeCashFlow", "Free Cash Flow"])
        current_fcf = annual_values[max(annual_values)] if annual_values else None

    current_pfcf = (
        current_market_cap / current_fcf
        if current_market_cap is not None and current_fcf is not None
        else None
    )
    fcf_history = _dated_row_values(annual_cashflow, ["FreeCashFlow", "Free Cash Flow"])
    pfcf_history = {}
    for date, market_cap in market_cap_history.items():
        free_cash_flow = _nearest_value(fcf_history, date)
        if free_cash_flow is not None:
            multiple = _positive_number(market_cap / free_cash_flow)
            if multiple is not None:
                pfcf_history[date] = multiple

    return {
        "current_pe": current_pe,
        "pe_history": _history_series(pe_history, "P/E"),
        "current_pfcf": _positive_number(current_pfcf),
        "pfcf_history": _history_series(pfcf_history, "P/FCF"),
    }
