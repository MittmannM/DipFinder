import os
from datetime import datetime, timedelta
import streamlit as st, pandas as pd, numpy as np, yfinance as yf
import plotly.express as px

API_KEY = os.getenv("ALPHA_VANTAGE_KEY")

st.title("Stock Tool")
ticker = st.text_input("Ticker").format()


@st.cache_data
def dl_yf_price(ticker, start_date, end_date):
    data = yf.download(ticker, start=start_date, end=end_date)
    return data


@st.cache_data
def dl_yf_info(ticker):
    data = yf.Ticker(ticker).info

    return data


def calc_valuation_metrics(ticker):
    data = dl_yf_info(ticker)

    price = 0
    market_cap = round(data['marketCap']/ 1000000000, 2)
    trailing_pe = round(data["trailingPE"], 2)
    forward_pe = round(data["forwardPE"], 2)
    fcf = yf.Ticker(ticker).cashflow.loc["Free Cash Flow"].iloc[0]
    fcf_yield = round((fcf / data['marketCap']) *100, 2)
    price_to_sales = round(data["priceToSalesTrailing12Months"], 2)
    price_to_book = round(data["priceToBook"], 2)
    cash = round(data["totalCash"]/ 1000000000, 2)
    debt = round(data["totalDebt"] / 1000000000, 2)
    net = round((data["totalCash"] - data["totalDebt"]) / 1000000000, 2)
    dividend_yield = round(data["dividendYield"] * 100, 2)
    dividend_rate = data["dividendRate"]
    shares_outstanding = data["sharesOutstanding"]
    fcf_payout = round(((dividend_rate * shares_outstanding) / fcf) * 100, 0)
    operating_margin = round(data["operatingMargins"] * 100, 2)
    profit_margin = round(data["profitMargins"] * 100, 2)

    return (price, market_cap, trailing_pe, forward_pe, fcf_yield, price_to_sales, price_to_book, cash, debt, net,
            dividend_yield, fcf_payout, operating_margin, profit_margin)


(price, market_cap, trailing_pe, forward_pe, fcf_yield, price_to_sales, price_to_book, cash, debt, net, dividend_yield,
 fcf_payout, operating_margin, profit_margin) = calc_valuation_metrics(ticker)

data = dl_yf_price(ticker, start_date=datetime.today() - timedelta(days=365 * 20), end_date=datetime.today())
fig = px.line(data, x=data.index, y=data["Adj Close"], title=f"{ticker.upper()} {'Todo: aktueller Kurs'}")
fig.layout.update(title_text="Stock Price", xaxis_rangeslider_visible=True)
st.plotly_chart(fig)
# Create columns
col1, col2, col3, col4 = st.columns(4)

# First column: Valuation section
with col1:
    st.write("### Valuation")
    st.write(f"Market Cap: {market_cap}B")
    st.write(f"Trailing PE: {trailing_pe}")
    st.write(f"Forward PE: {forward_pe}")
    st.write(f"Price/Sales: {price_to_sales}")
    st.write(f"Price/Book: {price_to_book}")
    st.write(f"FCF Yield: {fcf_yield}%")

# Second column: Balance section
with col2:
    st.write("### Balance")
    st.write(f"Cash: {cash}B")
    st.write(f"Debt: {debt}B")
    st.write(f"Net: {net}B")


with col3:
    st.write("### Dividend")
    st.write(f"Dividend Yield: {dividend_yield}%")
    st.write(f"FCF Payout: {fcf_payout}%")

with col4:
    st.write("### Margins")
    st.write(f"Profit Margin: {profit_margin}%")
    st.write(f"Operating Margin: {operating_margin}%")


tabs = ["Revenue", "EBITDA", "Free Cash Flow", "Net Income", "EPS", "Cash&Debt", "Dividends", "ROIC", ]
