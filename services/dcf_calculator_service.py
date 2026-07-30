from datetime import datetime
import math

import pandas as pd


FORECAST_YEARS = 5


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _frame_series(frame, column):
    if frame is None or frame.empty or "Date" not in frame.columns or column not in frame.columns:
        return {}

    values = {}
    for _, row in frame[["Date", column]].iterrows():
        year = _number(row["Date"])
        value = _number(row[column])
        if year is not None and value is not None:
            values[int(year)] = value
    return values


def _annual_growth_values(values):
    growth = []
    ordered = sorted(values.items())
    for (previous_year, previous), (current_year, current) in zip(ordered, ordered[1:]):
        if current_year - previous_year != 1 or previous <= 0 or current <= 0:
            continue
        growth.append((current - previous) / previous)
    return growth


def _period_average(values, periods, positive_only=False):
    clean = [
        value
        for value in (_number(item) for item in values)
        if value is not None and (not positive_only or value > 0)
    ]
    if len(clean) < periods:
        return None
    return sum(clean[-periods:]) / periods


def calculate_historical_dcf_benchmarks(fundamental_history):
    """Calculate exact 5Y/10Y averages from annual fundamental observations."""
    empty_result = {
        "eps_growth_5y": None,
        "eps_growth_10y": None,
        "fcf_growth_5y": None,
        "fcf_growth_10y": None,
        "pe_average_5y": None,
        "pe_average_10y": None,
        "pfcf_average_5y": None,
        "pfcf_average_10y": None,
        "fcf_yield_average_5y": None,
        "fcf_yield_average_10y": None,
        "fcf_growth_basis": None,
    }
    if fundamental_history is None or fundamental_history.empty:
        return empty_result

    eps = _frame_series(fundamental_history, "EPS Diluted")
    free_cash_flow = _frame_series(fundamental_history, "Free Cash Flow")
    shares = _frame_series(fundamental_history, "Shares Outstanding")
    fcf_per_share = {
        year: value / shares[year]
        for year, value in free_cash_flow.items()
        if year in shares and value > 0 and shares[year] > 0
    }
    if len(fcf_per_share) >= 2:
        fcf_growth_values = _annual_growth_values(fcf_per_share)
        fcf_growth_basis = "FCF/share"
    else:
        fcf_growth_values = _annual_growth_values(free_cash_flow)
        fcf_growth_basis = "FCF"

    eps_growth_values = _annual_growth_values(eps)
    pe_values = [
        value
        for _, value in sorted(_frame_series(fundamental_history, "PE Ratio").items())
    ]
    pfcf_values = [
        value
        for _, value in sorted(_frame_series(fundamental_history, "P/FCF Ratio").items())
    ]
    fcf_yields = [1 / value for value in pfcf_values if value > 0]

    return {
        "eps_growth_5y": _period_average(eps_growth_values, 5),
        "eps_growth_10y": _period_average(eps_growth_values, 10),
        "fcf_growth_5y": _period_average(fcf_growth_values, 5),
        "fcf_growth_10y": _period_average(fcf_growth_values, 10),
        "pe_average_5y": _period_average(pe_values, 5, positive_only=True),
        "pe_average_10y": _period_average(pe_values, 10, positive_only=True),
        "pfcf_average_5y": _period_average(pfcf_values, 5, positive_only=True),
        "pfcf_average_10y": _period_average(pfcf_values, 10, positive_only=True),
        "fcf_yield_average_5y": _period_average(fcf_yields, 5, positive_only=True),
        "fcf_yield_average_10y": _period_average(fcf_yields, 10, positive_only=True),
        "fcf_growth_basis": fcf_growth_basis,
    }


def build_dcf_inputs(
    ticker,
    fundamental_history=None,
    ticker_info=None,
    analyst_eps_growth=None,
    analyst_growth_source=None,
    trailing_free_cash_flow=None,
    fallback_current_price=None,
):
    symbol = str(ticker).strip().upper()
    if not symbol:
        raise ValueError("Ticker must not be empty.")

    info = ticker_info if isinstance(ticker_info, dict) else {}

    current_price = _number(info.get("currentPrice") or info.get("regularMarketPrice"))
    if current_price is None:
        current_price = _number(fallback_current_price)

    trailing_eps = _number(info.get("trailingEps"))
    trailing_pe = _number(info.get("trailingPE"))
    shares_outstanding = _number(info.get("sharesOutstanding"))
    market_cap = _number(info.get("marketCap"))
    free_cash_flow = _number(trailing_free_cash_flow)
    if free_cash_flow is None:
        free_cash_flow = _number(info.get("freeCashflow"))
    implied_share_count = (
        market_cap / current_price
        if market_cap is not None and current_price not in (None, 0)
        else shares_outstanding
    )
    fcf_per_share = (
        free_cash_flow / implied_share_count
        if free_cash_flow is not None and implied_share_count not in (None, 0)
        else None
    )
    current_fcf_yield = (
        free_cash_flow / market_cap
        if free_cash_flow is not None and market_cap not in (None, 0)
        else None
    )
    if current_fcf_yield is None and fcf_per_share is not None and current_price not in (None, 0):
        current_fcf_yield = fcf_per_share / current_price

    historical_benchmarks = calculate_historical_dcf_benchmarks(fundamental_history)
    eps_growth = _number(analyst_eps_growth)
    eps_growth_source = analyst_growth_source
    if eps_growth is None:
        eps_growth = _number(info.get("earningsGrowth"))
        if eps_growth is not None:
            eps_growth_source = "Yahoo earnings growth"
    if eps_growth is None:
        eps_growth = historical_benchmarks["eps_growth_5y"]
        if eps_growth is None:
            eps_growth = historical_benchmarks["eps_growth_10y"]
        if eps_growth is not None:
            eps_growth_source = "Shared annual fundamentals"

    fcf_growth = historical_benchmarks["fcf_growth_5y"]
    if fcf_growth is None:
        fcf_growth = historical_benchmarks["fcf_growth_10y"]
    fcf_growth_source = None
    if fcf_growth is not None:
        fcf_growth_source = (
            f"Shared annual {historical_benchmarks['fcf_growth_basis']} history"
        )

    return {
        "ticker": symbol,
        "name": info.get("longName") or info.get("shortName") or symbol,
        "currency": info.get("currency") or info.get("financialCurrency") or "",
        "current_price": current_price,
        "trailing_eps": trailing_eps,
        "trailing_pe": trailing_pe,
        "eps_growth": eps_growth,
        "eps_growth_source": eps_growth_source,
        "fcf_per_share": fcf_per_share,
        "current_fcf_yield": current_fcf_yield,
        "fcf_growth": fcf_growth,
        "fcf_growth_source": fcf_growth_source,
        **historical_benchmarks,
        "historical_source": (
            fundamental_history.attrs.get("source")
            if fundamental_history is not None
            else None
        ),
        "updated_at": datetime.now().astimezone(),
    }


def calculate_dcf_projection(
    current_price,
    current_metric_per_share,
    annual_growth_rate,
    current_assumption,
    terminal_assumption,
    basis,
    years=FORECAST_YEARS,
):
    price = _number(current_price)
    metric = _number(current_metric_per_share)
    growth = _number(annual_growth_rate)
    current_terminal = _number(current_assumption)
    terminal = _number(terminal_assumption)

    if price is None or price <= 0:
        raise ValueError("Current price must be positive.")
    if metric is None or metric <= 0:
        raise ValueError("The current TTM value per share must be positive.")
    if growth is None or growth <= -1:
        raise ValueError("Annual growth must be greater than -100%.")
    if current_terminal is None or current_terminal <= 0 or terminal is None or terminal <= 0:
        raise ValueError("Current and terminal valuation assumptions must be positive.")
    if basis not in {"EPS", "FCF"}:
        raise ValueError("Basis must be EPS or FCF.")

    projection = []
    for year in range(years + 1):
        future_metric = metric * (1 + growth) ** year
        weight = year / years
        assumption = current_terminal + (terminal - current_terminal) * weight
        projected_price = future_metric * assumption if basis == "EPS" else future_metric / assumption
        if year == 0:
            projected_price = price
        projection.append(
            {
                "year": year,
                "metric_per_share": future_metric,
                "valuation_assumption": assumption,
                "projected_price": projected_price,
            }
        )
    return projection


def calculate_dcf_scenario(
    current_price,
    current_metric_per_share,
    annual_growth_rate,
    terminal_assumption,
    desired_annual_return,
    basis,
    years=FORECAST_YEARS,
):
    price = _number(current_price)
    metric = _number(current_metric_per_share)
    growth = _number(annual_growth_rate)
    terminal = _number(terminal_assumption)
    desired_return = _number(desired_annual_return)

    if price is None or price <= 0:
        raise ValueError("Current price must be positive.")
    if metric is None or metric <= 0:
        raise ValueError("The current TTM value per share must be positive.")
    if growth is None or growth <= -1:
        raise ValueError("Annual growth must be greater than -100%.")
    if terminal is None or terminal <= 0:
        raise ValueError("The terminal assumption must be positive.")
    if desired_return is None or desired_return <= -1:
        raise ValueError("Desired annual return must be greater than -100%.")
    if not isinstance(years, int) or years <= 0:
        raise ValueError("Forecast years must be a positive integer.")

    future_metric = metric * (1 + growth) ** years
    if basis == "EPS":
        future_price = future_metric * terminal
    elif basis == "FCF":
        future_price = future_metric / terminal
    else:
        raise ValueError("Basis must be EPS or FCF.")

    multiple = future_price / price
    annual_return = multiple ** (1 / years) - 1
    total_return = multiple - 1
    maximum_purchase_price = future_price / (1 + desired_return) ** years

    return {
        "future_metric_per_share": future_metric,
        "future_price": future_price,
        "annual_return": annual_return,
        "total_return": total_return,
        "multiple": multiple,
        "maximum_purchase_price": maximum_purchase_price,
    }
