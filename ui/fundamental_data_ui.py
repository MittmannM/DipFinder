import pandas as pd
import streamlit as st

from repositories import stock_data_repository as repository


def load_fundamental_history(ticker, markets_sh_token):
    try:
        frame = repository.get_annual_fundamentals(ticker, markets_sh_token)
    except Exception as exc:
        st.error(f"No historical financial data available for {ticker}: {exc}")
        return pd.DataFrame()

    for warning in frame.attrs.get("warnings", []):
        if warning.startswith("Set the ") or "returned only" in warning:
            st.info(warning)
        else:
            st.warning(warning)
    return frame
