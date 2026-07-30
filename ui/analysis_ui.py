import plotly.express as px
import streamlit as st

from repositories import stock_data_repository as repository
from services.fundamental_analysis_service import (
    calculate_average_growth_rates,
    calculate_valuation_metrics,
    calculate_yoy_growth_rates,
    to_number,
)
from ui.fundamental_data_ui import load_fundamental_history


DIRECT_GROWTH_CHARTS = (
    ("Revenue", "Revenue Growth", "Revenue", "#CC8124"),
    ("Free Cash Flow", "Free Cash Flow Growth", "Free Cash Flow", "#2EBD2E"),
    ("EPS Diluted", "EPS Diluted Growth", "EPS Diluted", "#C0B607"),
    ("EBITDA", "EBITDA Growth", "EBITDA", "#71BACB"),
    ("Net Income", "Net Income Growth", "Net Income", "#BB9E81"),
    ("Dividends", "Dividends PS Growth", "Dividends", "#22673D"),
    (
        "Shares Outstanding",
        "Shares Outstanding Growth",
        "Shares Outstanding",
        "#15A1B1",
    ),
)

DERIVED_GROWTH_CHARTS = (
    ("Net Debt", "Net Debt", "#C40824"),
    ("ROCE", "ROCE", "#896263"),
    ("ROIC", "ROIC", "#4682B4"),
)


def _fallback_free_cash_flow(ticker, ticker_info):
    if to_number(ticker_info.get("freeCashflow")) is not None:
        return None
    cashflow = repository.get_annual_cashflow(ticker)
    for row_name in ("Free Cash Flow", "FreeCashFlow"):
        try:
            return to_number(cashflow.loc[row_name].iloc[0])
        except (KeyError, IndexError, TypeError):
            continue
    return None


def _valuation_metrics(ticker):
    ticker_info = repository.get_ticker_info(ticker)
    fallback_free_cash_flow = _fallback_free_cash_flow(ticker, ticker_info)
    dividend_calendar = None
    if (to_number(ticker_info.get("dividendRate")) or 0) > 0:
        try:
            dividend_calendar = repository.get_dividend_calendar(ticker)
        except Exception:
            dividend_calendar = None
    return calculate_valuation_metrics(
        ticker_info,
        fallback_free_cash_flow=fallback_free_cash_flow,
        dividend_calendar=dividend_calendar,
    )


def _render_overview(metrics):
    valuation, balance, dividend, margins = st.columns(4)
    with valuation:
        st.write("### Valuation")
        st.write(f"Market Cap: {metrics['market_cap']}B")
        st.write(f"Trailing PE: {metrics['trailing_pe']}")
        st.write(f"Forward PE: {metrics['forward_pe']}")
        st.write(f"EV/EBITDA: {metrics['enterprise_to_ebitda']}")
        st.write(f"Price/Sales: {metrics['price_to_sales']}")
        st.write(f"Price/Book: {metrics['price_to_book']}")
        st.write(f"FCF Yield: {metrics['fcf_yield']}%")
    with balance:
        st.write("### Balance")
        st.write(f"Cash: {metrics['cash']}B")
        st.write(f"Debt: {metrics['debt']}B")
        st.write(f"Net: {metrics['net']}B")
    with dividend:
        st.write("### Dividend")
        st.write(f"Dividend Yield: {metrics['dividend_yield']}%")
        st.write(f"FCF Payout: {metrics['fcf_payout']}%")
        st.write(f"Next Payout: {metrics['next_dividend']}")
    with margins:
        st.write("### Margins")
        st.write(f"Profit Margin: {metrics['profit_margin']}%")
        st.write(f"Operating Margin: {metrics['operating_margin']}%")


def _render_bar_chart(frame, value_column, title, color, growth_values):
    one_year, two_year, five_year, ten_year = calculate_average_growth_rates(
        growth_values
    )
    figure = px.bar(
        frame,
        x="Date",
        y=value_column,
        title=title,
        color_discrete_sequence=[color],
        labels={
            "Date": (
                f"1Y: {one_year}% 2Y: {two_year}% "
                f"5Y: {five_year}% 10Y: {ten_year}%"
            )
        },
    )
    figure.update_layout(
        title_font=dict(color=color, size=30),
        xaxis_title_font=dict(color="#2B824C", size=22),
        yaxis_title=None,
    )
    st.plotly_chart(figure)


def _render_fundamental_charts(frame):
    left, right = st.columns(2)
    direct_left = DIRECT_GROWTH_CHARTS[:3]
    direct_right = DIRECT_GROWTH_CHARTS[3:]

    with left:
        for value_column, growth_column, title, color in direct_left:
            _render_bar_chart(
                frame,
                value_column,
                title,
                color,
                frame[growth_column].tolist(),
            )
        for value_column, title, color in DERIVED_GROWTH_CHARTS[:2]:
            _render_bar_chart(
                frame,
                value_column,
                title,
                color,
                calculate_yoy_growth_rates(frame[value_column]),
            )

    with right:
        for value_column, growth_column, title, color in direct_right:
            _render_bar_chart(
                frame,
                value_column,
                title,
                color,
                frame[growth_column].tolist(),
            )
        for value_column, title, color in DERIVED_GROWTH_CHARTS[2:]:
            _render_bar_chart(
                frame,
                value_column,
                title,
                color,
                calculate_yoy_growth_rates(frame[value_column]),
            )


def render_analysis(ticker, years, markets_sh_token):
    metrics = _valuation_metrics(ticker)
    st.title(ticker.upper())

    price_history = repository.get_price_history(ticker)
    if price_history.empty or "Adjusted Close" not in price_history.columns:
        st.warning(f"No price history available for {ticker}.")
    else:
        price_data = price_history.reset_index()
        date_column = price_data.columns[0]
        price_graph = px.line(price_data, x=date_column, y="Adjusted Close")
        price_graph.layout.update(
            title_text=None,
            xaxis_rangeslider_visible=True,
            yaxis_title=None,
        )
        st.plotly_chart(price_graph)

    _render_overview(metrics)

    fundamentals = load_fundamental_history(ticker, markets_sh_token)
    if fundamentals.empty:
        return
    if fundamentals.attrs.get("source_symbol"):
        st.caption(
            f"Historical fundamentals: {fundamentals.attrs['source']} / "
            f"{fundamentals.attrs['source_symbol']}"
        )

    _render_fundamental_charts(fundamentals.tail(years).reset_index(drop=True))
