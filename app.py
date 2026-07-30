import os

import streamlit as st

from ui.analysis_ui import render_analysis
from ui.dcf_calculator_ui import render_dcf_calculator
from ui.watchlist_ui import render_watchlist


st.set_page_config(layout="wide")

ticker = st.sidebar.text_input("Enter stock ticker:", "V")
input_years = st.sidebar.selectbox(
    "Select number of years to look at:",
    options=[10, 15, 20],
)
markets_sh_token = os.getenv("MARKETS_SH_API_TOKEN", "").strip()

active_view = st.segmented_control(
    "View",
    options=["Analysis", "Watchlist", "DCF Calculator"],
    default="Analysis",
    required=True,
    key="main_view",
    label_visibility="collapsed",
    width="stretch",
)

if active_view == "Analysis":
    render_analysis(ticker, input_years, markets_sh_token)
elif active_view == "Watchlist":
    render_watchlist()
else:
    render_dcf_calculator(ticker, markets_sh_token)
