import streamlit as st

from repositories import stock_data_repository, watchlist_repository
from ui.watchlist_dip_finder_ui import render_watchlist_dip_finder


def _resolve_ticker(ticker):
    try:
        info = stock_data_repository.get_ticker_info(ticker)
    except Exception:
        return None
    if not isinstance(info, dict):
        return None

    name = info.get("longName") or info.get("shortName")
    quote_type = str(info.get("quoteType") or "").upper()
    if not name or quote_type == "NONE":
        return None
    return {"ticker": ticker, "name": str(name).strip()}


def _add_ticker(new_ticker):
    ticker = watchlist_repository.normalize_ticker(new_ticker)
    watchlist = watchlist_repository.load_watchlist()
    if ticker is None:
        st.error("Enter a valid ticker.")
        return
    if any(entry["ticker"] == ticker for entry in watchlist):
        st.info(f"{ticker} is already on the watchlist.")
        return

    with st.spinner(f"Checking {ticker} with Yahoo Finance..."):
        security = _resolve_ticker(ticker)
    if security is None:
        st.error(f"Yahoo Finance could not find {ticker}.")
        return

    watchlist.append(security)
    watchlist_repository.save_watchlist(watchlist)
    st.session_state["watchlist_notice"] = (
        f"Added {security['name']} ({ticker})."
    )
    st.rerun()


def _fill_missing_names(watchlist):
    changed = False
    for entry in watchlist:
        if entry["name"] is not None:
            continue
        security = _resolve_ticker(entry["ticker"])
        if security is not None:
            entry["name"] = security["name"]
            changed = True
    if changed:
        watchlist_repository.save_watchlist(watchlist)


def _render_entries(watchlist):
    for entry in watchlist:
        ticker = entry["ticker"]
        ticker_column, remove_column = st.columns([5, 1], vertical_alignment="center")
        ticker_column.markdown(
            f"**{entry['name']}**" if entry["name"] else "**Name unavailable**"
        )
        ticker_column.caption(ticker)

        if remove_column.button("Remove", key=f"remove_{ticker}", use_container_width=True):
            watchlist_repository.save_watchlist(
                [item for item in watchlist if item["ticker"] != ticker]
            )
            st.session_state["watchlist_notice"] = f"Removed {ticker}."
            st.rerun()


def render_watchlist():
    st.subheader("Watchlist")
    notice = st.session_state.pop("watchlist_notice", None)
    if notice:
        st.success(notice)

    with st.form("watchlist_add_form", clear_on_submit=True):
        input_column, button_column = st.columns([5, 1], vertical_alignment="bottom")
        new_ticker = input_column.text_input(
            "Ticker",
            placeholder="e.g. V, SAP.DE, ASML.AS",
            label_visibility="collapsed",
        )
        add_ticker = button_column.form_submit_button("Add", use_container_width=True)
    if add_ticker:
        _add_ticker(new_ticker)

    watchlist = watchlist_repository.load_watchlist()
    if not watchlist:
        st.info("The watchlist is empty.")
        return

    _fill_missing_names(watchlist)
    _render_entries(watchlist)
    st.divider()
    render_watchlist_dip_finder(watchlist)
