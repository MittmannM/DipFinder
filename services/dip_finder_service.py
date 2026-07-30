import math

import pandas as pd


PERIOD_LABELS = ("1W", "1M", "3M", "6M", "YTD", "1Y")


def _valid_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _price_series(price_history):
    if isinstance(price_history, pd.Series):
        prices = price_history.copy()
    elif isinstance(price_history, pd.DataFrame) and "Adjusted Close" in price_history.columns:
        prices = price_history["Adjusted Close"].copy()
    else:
        return pd.Series(dtype="float64")

    prices = pd.to_numeric(prices, errors="coerce").dropna()
    if prices.empty:
        return prices
    prices.index = pd.to_datetime(prices.index, utc=True).tz_convert(None)
    return prices[~prices.index.duplicated(keep="last")].sort_index()


def _start_price(prices, target_date):
    candidates = prices.loc[prices.index <= target_date]
    if candidates.empty:
        candidates = prices.loc[prices.index >= target_date]
        return _valid_number(candidates.iloc[0]) if not candidates.empty else None
    return _valid_number(candidates.iloc[-1])


def calculate_period_returns(price_history):
    prices = _price_series(price_history)
    if prices.empty:
        return {period: None for period in PERIOD_LABELS}

    current_price = _valid_number(prices.iloc[-1])
    current_date = prices.index[-1]
    targets = {
        "1W": current_date - pd.DateOffset(weeks=1),
        "1M": current_date - pd.DateOffset(months=1),
        "3M": current_date - pd.DateOffset(months=3),
        "6M": current_date - pd.DateOffset(months=6),
        "YTD": pd.Timestamp(year=current_date.year, month=1, day=1),
        "1Y": current_date - pd.DateOffset(years=1),
    }

    returns = {}
    for period, target_date in targets.items():
        start_price = _start_price(prices, target_date)
        returns[period] = (
            current_price / start_price - 1
            if current_price is not None and start_price not in (None, 0)
            else None
        )
    return returns


def calculate_52_week_metrics(price_history):
    prices = _price_series(price_history)
    empty = {
        "high_52w": None,
        "low_52w": None,
        "drawdown_52w": None,
        "range_position_52w": None,
    }
    if prices.empty:
        return empty

    current_date = prices.index[-1]
    recent = prices.loc[prices.index >= current_date - pd.DateOffset(years=1)]
    if recent.empty:
        return empty

    current_price = _valid_number(prices.iloc[-1])
    high_52w = _valid_number(recent.max())
    low_52w = _valid_number(recent.min())
    if current_price is None or high_52w in (None, 0) or low_52w is None:
        return empty

    price_range = high_52w - low_52w
    return {
        "high_52w": high_52w,
        "low_52w": low_52w,
        "drawdown_52w": current_price / high_52w - 1,
        "range_position_52w": (
            (current_price - low_52w) / price_range if price_range != 0 else None
        ),
    }


def determine_dip_status(metrics):
    period_returns = metrics.get("period_returns") or {}
    one_month = _valid_number(period_returns.get("1M"))
    drawdown = _valid_number(metrics.get("drawdown_52w"))

    if one_month is None or drawdown is None:
        return "INSUFFICIENT_DATA"

    pe_percentile = _valid_number(metrics.get("pe_percentile"))
    pfcf_percentile = _valid_number(metrics.get("pfcf_percentile"))
    if pe_percentile is None or pfcf_percentile is None:
        return "INSUFFICIENT_DATA"

    dip_condition = one_month <= -0.08 or drawdown <= -0.20
    if not dip_condition:
        return "NO_DIP"

    if pe_percentile <= 0.35 or pfcf_percentile <= 0.35:
        return "ATTRACTIVE_DIP"
    if pe_percentile > 0.65 and pfcf_percentile > 0.65:
        return "DIP_BUT_EXPENSIVE"
    return "DIP"
