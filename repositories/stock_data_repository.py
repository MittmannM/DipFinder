import streamlit as st

from providers import markets_sh_provider as markets_sh
from providers import stock_analysis_provider as stock_analysis
from providers import yahoo_finance_provider as yahoo
from services.dcf_calculator_service import build_dcf_inputs


CACHE_TTL_SECONDS = 60 * 60
FUNDAMENTAL_HISTORY_YEARS = 20
PRICE_HISTORY_YEARS = 20


def _symbol(ticker):
    symbol = str(ticker).strip().upper()
    if not symbol:
        raise ValueError("Ticker must not be empty.")
    return symbol


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_ticker_info(symbol):
    return yahoo.get_ticker_info(symbol)


def get_ticker_info(ticker):
    return _get_ticker_info(_symbol(ticker))


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_dividend_calendar(symbol):
    return yahoo.get_dividend_calendar(symbol)


def get_dividend_calendar(ticker):
    return _get_dividend_calendar(_symbol(ticker))


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_annual_cashflow(symbol):
    return yahoo.get_annual_cashflow(symbol)


def get_annual_cashflow(ticker):
    return _get_annual_cashflow(_symbol(ticker))


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_price_history(symbol):
    return yahoo.get_price_history(symbol, years=PRICE_HISTORY_YEARS)


def get_price_history(ticker):
    return _get_price_history(_symbol(ticker))


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_annual_fundamentals(ticker, has_api_token, _api_token):
    symbol = _symbol(ticker)
    frame = None
    warnings = []

    if has_api_token:
        try:
            frame = markets_sh.get_annual_fundamentals(
                symbol,
                _api_token,
                FUNDAMENTAL_HISTORY_YEARS,
            )
        except Exception as exc:
            warnings.append(f"markets.sh failed for {symbol}: {exc}")
    else:
        warnings.append(
            "Set the MARKETS_SH_API_TOKEN environment variable before starting Streamlit "
            "to load global fundamentals."
        )

    if frame is None or frame.empty:
        try:
            frame = stock_analysis.get_annual_fundamentals(
                symbol,
                FUNDAMENTAL_HISTORY_YEARS,
            )
        except Exception as exc:
            warnings.append(
                f"StockAnalysis fallback failed for {symbol}: {exc}. "
                "Falling back to Yahoo Finance."
            )
            frame = yahoo.get_annual_fundamentals(
                symbol,
                FUNDAMENTAL_HISTORY_YEARS,
            )

    if frame is None or frame.empty:
        raise RuntimeError(f"No historical financial data available for {symbol}.")

    frame = frame.copy()
    if len(frame) < FUNDAMENTAL_HISTORY_YEARS:
        warnings.append(
            f"{frame.attrs.get('source', 'The provider')} returned only "
            f"{len(frame)} annual periods for {symbol}."
        )
    frame.attrs["warnings"] = warnings
    return frame


def get_annual_fundamentals(ticker, api_token=""):
    token = str(api_token or "").strip()
    return _get_annual_fundamentals(_symbol(ticker), bool(token), token)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_fundamental_history(symbol):
    return yahoo.get_valuation_history(symbol, ticker_info=get_ticker_info(symbol))


def get_fundamental_history(ticker):
    return _get_fundamental_history(_symbol(ticker))


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_analyst_eps_growth(symbol):
    return yahoo.get_analyst_eps_growth(symbol)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_trailing_free_cash_flow(symbol):
    return yahoo.get_trailing_free_cash_flow(symbol)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def _get_dcf_calculator_inputs(symbol, fundamental_history):
    info = get_ticker_info(symbol)
    analyst_growth, analyst_source = _get_analyst_eps_growth(symbol)
    free_cash_flow = _number(info.get("freeCashflow"))
    if free_cash_flow is None:
        free_cash_flow = _get_trailing_free_cash_flow(symbol)

    fallback_price = None
    if _number(info.get("currentPrice") or info.get("regularMarketPrice")) is None:
        price_history = get_price_history(symbol)
        if not price_history.empty:
            fallback_price = _number(price_history["Adjusted Close"].iloc[-1])

    return build_dcf_inputs(
        symbol,
        fundamental_history=fundamental_history,
        ticker_info=info,
        analyst_eps_growth=analyst_growth,
        analyst_growth_source=analyst_source,
        trailing_free_cash_flow=free_cash_flow,
        fallback_current_price=fallback_price,
    )


def get_dcf_calculator_inputs(ticker, fundamental_history):
    return _get_dcf_calculator_inputs(_symbol(ticker), fundamental_history)


def clear_dcf_cache():
    _get_dcf_calculator_inputs.clear()
    _get_ticker_info.clear()
    _get_analyst_eps_growth.clear()
    _get_trailing_free_cash_flow.clear()


def clear_watchlist_caches():
    _get_price_history.clear()
    _get_fundamental_history.clear()
    _get_ticker_info.clear()


def clear_all_caches():
    _get_ticker_info.clear()
    _get_dividend_calendar.clear()
    _get_annual_cashflow.clear()
    _get_price_history.clear()
    _get_annual_fundamentals.clear()
    _get_fundamental_history.clear()
    _get_analyst_eps_growth.clear()
    _get_trailing_free_cash_flow.clear()
    _get_dcf_calculator_inputs.clear()
