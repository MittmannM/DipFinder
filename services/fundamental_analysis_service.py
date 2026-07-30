import math


def to_number(value):
    if value in (None, "", "None"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_divide(numerator, denominator):
    numerator = to_number(numerator)
    denominator = to_number(denominator)
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def calculate_average_growth_rates(growth_values):
    clean_growth = [
        number
        for value in growth_values
        if (number := to_number(value)) is not None
    ]

    def average(period):
        values = clean_growth[-period:]
        return round((sum(values) / len(values)) * 100, 2) if values else 0

    return average(1), average(2), average(5), average(10)


def calculate_yoy_growth_rates(values):
    growth = []
    for index in range(len(values) - 1):
        previous = to_number(values.iloc[index] if hasattr(values, "iloc") else values[index])
        current = to_number(
            values.iloc[index + 1] if hasattr(values, "iloc") else values[index + 1]
        )
        if previous in (None, 0) or current is None:
            growth.append(None)
        else:
            growth.append((current - previous) / abs(previous))
    return growth


def calculate_valuation_metrics(
    ticker_info,
    fallback_free_cash_flow=None,
    dividend_calendar=None,
):
    info = ticker_info if isinstance(ticker_info, dict) else {}

    def rounded_value(key, digits=2):
        value = to_number(info.get(key))
        return round(value, digits) if value is not None else 0

    market_cap_value = to_number(info.get("marketCap")) or 0
    cash_value = to_number(info.get("totalCash")) or 0
    debt_value = to_number(info.get("totalDebt")) or 0
    enterprise_value = to_number(info.get("enterpriseValue"))
    ebitda_value = to_number(info.get("ebitda"))
    free_cash_flow = to_number(info.get("freeCashflow"))
    if free_cash_flow is None:
        free_cash_flow = to_number(fallback_free_cash_flow)
    free_cash_flow = free_cash_flow or 0

    enterprise_to_ebitda = to_number(info.get("enterpriseToEbitda"))
    if enterprise_to_ebitda is None:
        enterprise_to_ebitda = safe_divide(enterprise_value, ebitda_value)

    dividend_rate = to_number(info.get("dividendRate")) or 0
    shares_outstanding = to_number(info.get("sharesOutstanding")) or 0
    next_dividend = "N/A"
    dividend_date = (
        dividend_calendar.get("Dividend Date")
        if isinstance(dividend_calendar, dict)
        else None
    )
    if dividend_rate > 0 and hasattr(dividend_date, "strftime"):
        next_dividend = dividend_date.strftime("%d/%m/%Y")

    return {
        "market_cap": round(market_cap_value / 1e9, 2),
        "trailing_pe": rounded_value("trailingPE"),
        "forward_pe": rounded_value("forwardPE"),
        "enterprise_to_ebitda": (
            round(enterprise_to_ebitda, 2) if enterprise_to_ebitda is not None else 0
        ),
        "fcf_yield": (
            round(safe_divide(free_cash_flow, market_cap_value) * 100, 2)
            if market_cap_value
            else 0
        ),
        "price_to_sales": rounded_value("priceToSalesTrailing12Months"),
        "price_to_book": rounded_value("priceToBook"),
        "cash": round(cash_value / 1e9, 2),
        "debt": round(debt_value / 1e9, 2),
        "net": round((cash_value - debt_value) / 1e9, 2),
        "dividend_yield": rounded_value("dividendYield"),
        "fcf_payout": (
            round(safe_divide(dividend_rate * shares_outstanding, free_cash_flow) * 100, 0)
            if free_cash_flow
            else 0
        ),
        "operating_margin": round((to_number(info.get("operatingMargins")) or 0) * 100, 2),
        "profit_margin": round((to_number(info.get("profitMargins")) or 0) * 100, 2),
        "next_dividend": next_dividend,
    }
