import os
from datetime import datetime
import streamlit as st, pandas as pd, numpy as np, yfinance as yf
import plotly.express as px

API_KEY = os.getenv("ALPHA_VANTAGE_KEY")

st.title("Stock Tool")
ticker = st.text_input("Ticker").format()


def calc_valuation_metrics(ticker):

    data = yf.Ticker(ticker).info

    price = 0
    market_cap = data['marketCap']
    trailing_pe = round(data["trailingPE"], 2)
    forward_pe = round(data["forwardPE"], 2)
    fcf = yf.Ticker(ticker).cashflow.loc["Free Cash Flow"].iloc[0]
    fcf_yield = round((fcf / market_cap) * 100, 2)
    price_to_sales = round(data["priceToSalesTrailing12Months"], 2)
    price_to_book = round(data["priceToBook"], 2)
    market_cap = str(round(market_cap /1000000000, 3)) + "B"

    return price, market_cap, trailing_pe, forward_pe, fcf_yield, price_to_sales, price_to_book


price, market_cap, trailing_pe, forward_pe, fcf_yield, price_to_sales, price_to_book = calc_valuation_metrics(ticker)

data = yf.download(ticker, start="2000-01-01", end=datetime.today())
fig = px.line(data, x=data.index, y=data["Adj Close"], title=f"{ticker.upper()} {'Todo: aktueller Kurs'}")
st.plotly_chart(fig)
st.write(f"Market Cap: {market_cap}")
st.write(f"Trailing PE: {trailing_pe}")
st.write(f"Forward PE: {forward_pe}")
st.write(f"Price to Sales: {price_to_sales}")
st.write(f"Price to Book: {price_to_book}")
st.write(f"FCF Yield: {fcf_yield}%")

tabs = ["Revenue", "EBITDA", "Free Cash Flow", "Net Income", "EPS", "Cash&Debt", "Dividends", "ROIC", ]
