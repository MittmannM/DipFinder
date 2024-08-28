import os
from datetime import datetime, timedelta
import streamlit as st, pandas as pd, numpy as np, yfinance as yf
import plotly.express as px
import StockAnalysis as SA

#TODO 1: Request an QuickFS umschreiben damit man alles gleichzeitig requested (sonst problem)
#TODO 2: Custom Zeiträume erlauben statt immer 10 Jahre
#TODO 2: Cash&Debt graph bauen der beides vergleichet
#TODO 4: Historische ROIC und ROCE wachstumsraten berechnen + graphen
#TODO 5: Sidebar ausprobieren (metrics und ticker eingabe)
#TODO 6: Aktuellen Stockprice anzeigen
#TODO 7:

API_KEY = os.getenv("ALPHA_VANTAGE_KEY")
default_ticker = "V"

st.title("Stock Tool")
ticker = st.text_input("Ticker").format()
if ticker == "":
    ticker = default_ticker


@st.cache_data
def dl_yf_price(ticker, start_date, end_date):
    data = yf.download(ticker, start=start_date, end=end_date)
    return data


@st.cache_data
def dl_yf_info(ticker):
    data = yf.Ticker(ticker).info

    return data


@st.cache_data
def dl_yf_calendar(ticker):
    data = yf.Ticker(ticker).calendar

    return data


@st.cache_data
def calc_valuation_metrics(ticker):
    data = dl_yf_info(ticker)

    price = 0
    market_cap = round(data['marketCap'] / 1000000000, 2)
    trailing_pe = round(data["trailingPE"], 2)
    forward_pe = round(data["forwardPE"], 2)
    fcf = yf.Ticker(ticker).cashflow.loc["Free Cash Flow"].iloc[0]
    fcf_yield = round((fcf / data['marketCap']) * 100, 2)
    price_to_sales = round(data["priceToSalesTrailing12Months"], 2)
    price_to_book = round(data["priceToBook"], 2)
    cash = round(data["totalCash"] / 1000000000, 2)
    debt = round(data["totalDebt"] / 1000000000, 2)
    net = round((data["totalCash"] - data["totalDebt"]) / 1000000000, 2)
    dividend_yield = round(data["dividendYield"] * 100, 2)
    dividend_rate = data["dividendRate"]
    shares_outstanding = data["sharesOutstanding"]
    fcf_payout = round(((dividend_rate * shares_outstanding) / fcf) * 100, 0)
    operating_margin = round(data["operatingMargins"] * 100, 2)
    profit_margin = round(data["profitMargins"] * 100, 2)
    next_dividend = dl_yf_calendar(ticker).get("Dividend Date").strftime("%d/%m/%Y")

    return (price, market_cap, trailing_pe, forward_pe, fcf_yield, price_to_sales, price_to_book, cash, debt, net,
            dividend_yield, fcf_payout, operating_margin, profit_margin, next_dividend)


@st.cache_data
def get_graph_data_from_quickfs(ticker):
    revenue = SA.call_api_single(ticker, "revenue", 10)["data"]
    revenue_growth = SA.call_api_single(ticker, "revenue_growth", 10)["data"]
    fcf = SA.call_api_single(ticker, "fcf", 10)["data"]
    fcf_growth = SA.call_api_single(ticker, "fcf_growth", 10)["data"]
    debt = SA.call_api_single(ticker, "st_debt", 10)["data"]
    eps_diluted = SA.call_api_single(ticker, "eps_diluted", 10)["data"]
    eps_diluted_growth = SA.call_api_single(ticker, "eps_diluted_growth", 10)["data"]
    dividends = SA.call_api_single(ticker, "dividends", 10)["data"]
    dividends_ps_growth = SA.call_api_single(ticker, "dividends_per_share_growth", 10)["data"]
    net_income = SA.call_api_single(ticker, "net_income", 10)["data"]
    net_income_growth = SA.call_api_single(ticker, "net_income_growth", 10)["data"]
    ebitda = SA.call_api_single(ticker, "ebitda", 10)["data"]
    ebitda_growth = SA.call_api_single(ticker, "ebitda_growth", 10)["data"]
    shares_outstanding = SA.call_api_single(ticker, "shares_diluted", 10)["data"]
    shares_outstanding_growth = SA.call_api_single(ticker, "shares_diluted_growth", 10)["data"]
    roce = SA.call_api_single(ticker, "roce", 10)["data"]
    roic = SA.call_api_single(ticker, "roic", 10)["data"]

    data = {
        "Date": ["2014", "2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023"],
        "Revenue": revenue,
        "Revenue Growth": revenue_growth,
        "Free Cash Flow": fcf,
        "Free Cash Flow Growth": fcf_growth,
        "Debt": debt,
        "EPS Diluted": eps_diluted,
        "EPS Diluted Growth": eps_diluted_growth,
        "Dividends": dividends,
        "Dividends PS Growth": dividends_ps_growth,
        "Net Income": net_income,
        "Net Income Growth": net_income_growth,
        "EBITDA": ebitda,
        "EBITDA Growth": ebitda_growth,
        "Shares Outstanding": shares_outstanding,
        "Shares Outstanding Growth": shares_outstanding_growth,
        "ROCE": roce,
        "ROIC": roic,
    }

    df = pd.DataFrame(data)
    return df


@st.cache_data
def calc_growth_rates(growth_list):

    one_year = growth_list[len(growth_list) - 1] * 100
    two_year = (growth_list[len(growth_list) - 1] + growth_list[len(growth_list) - 2]) / 2 * 100
    five_year = (growth_list[len(growth_list) - 5] + growth_list[len(growth_list) - 4] + growth_list[
        len(growth_list) - 3] + growth_list[len(growth_list) - 2] + growth_list[len(growth_list) - 1]) / 5 * 100

    ten_year = sum(growth_list) / 10 * 100

    return round(one_year, 2), round(two_year, ), round(five_year, 2), round(ten_year, 2)


(price, market_cap, trailing_pe, forward_pe, fcf_yield, price_to_sales, price_to_book, cash, debt, net, dividend_yield,
 fcf_payout, operating_margin, profit_margin, next_dividend) = calc_valuation_metrics(ticker)

data = dl_yf_price(ticker, start_date=datetime.today() - timedelta(days=365 * 20), end_date=datetime.today())
price_graph = px.line(data, x=data.index, y=data["Adj Close"], title=f"{ticker.upper()} {'Todo: aktueller Kurs'}")
price_graph.layout.update(title_text=f"{ticker.upper()}", xaxis_rangeslider_visible=True)
st.plotly_chart(price_graph)

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
    st.write(f"Next Payout: {next_dividend}")

with col4:
    st.write("### Margins")
    st.write(f"Profit Margin: {profit_margin}%")
    st.write(f"Operating Margin: {operating_margin}%")

df = get_graph_data_from_quickfs(ticker)


one_year, two_year, five_year, ten_year = calc_growth_rates(df["Revenue Growth"].tolist())
revenue_graph = px.bar(df, x=df["Date"], y=df["Revenue"], title="Revenue (USD)", color_discrete_sequence=["orange"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
revenue_graph.update_layout(title_font=dict(color="orange"), xaxis_title_font=dict(color="#28A745"),
                            yaxis_title_font=dict(color="orange"))
st.plotly_chart(revenue_graph)


one_year, two_year, five_year, ten_year = calc_growth_rates(df["EBITDA Growth"].tolist())
ebitda_graph = px.bar(df, x=df["Date"], y=df["EBITDA"], title="EBITDA (USD)", color_discrete_sequence=["blue"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
ebitda_graph.update_layout(title_font=dict(color="blue"), xaxis_title_font=dict(color="#28A745"),
                            yaxis_title_font=dict(color="blue"))
st.plotly_chart(ebitda_graph)


one_year, two_year, five_year, ten_year = calc_growth_rates(df["Free Cash Flow Growth"].tolist())
free_cashflow_graph = px.bar(df, x=df["Date"], y=df["Free Cash Flow"], title="Free Cash Flow (USD)", color_discrete_sequence=["#006400"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
free_cashflow_graph.update_layout(title_font=dict(color="#006400"), xaxis_title_font=dict(color="#28A745"),
                            yaxis_title_font=dict(color="#006400"))
st.plotly_chart(free_cashflow_graph)


one_year, two_year, five_year, ten_year = calc_growth_rates(df["Net Income Growth"].tolist())
net_income_graph = px.bar(df, x=df["Date"], y=df["Net Income"], title="Net Income (USD)", color_discrete_sequence=["#FF4500"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
net_income_graph.update_layout(title_font=dict(color="#FF4500"), xaxis_title_font=dict(color="#28A745"),
                            yaxis_title_font=dict(color="#FF4500"))
st.plotly_chart(net_income_graph)


one_year, two_year, five_year, ten_year = calc_growth_rates(df["EPS Diluted Growth"].tolist())
eps_graph = px.bar(df, x=df["Date"], y=df["EPS Diluted"], title="EPS Diluted (USD)", color_discrete_sequence=["yellow"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
eps_graph.update_layout(title_font=dict(color="yellow"), xaxis_title_font=dict(color="#28A745"),
                            yaxis_title_font=dict(color="yellow"))
st.plotly_chart(eps_graph)


one_year, two_year, five_year, ten_year = calc_growth_rates(df["Dividends PS Growth"].tolist())
dividends_graph = px.bar(df, x=df["Date"], y=df["Dividends"], title="Dividends (USD)", color_discrete_sequence=["#28A745"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
dividends_graph.update_layout(title_font=dict(color="#28A745"), xaxis_title_font=dict(color="#28A745"),
                            yaxis_title_font=dict(color="#28A745"))
st.plotly_chart(dividends_graph)


one_year, two_year, five_year, ten_year = calc_growth_rates(df["Shares Outstanding Growth"].tolist())
shares_outstanding_graph = px.bar(df, x=df["Date"], y=df["Shares Outstanding"], title="Shares Outstanding", color_discrete_sequence=["#40E0D0"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
shares_outstanding_graph.update_layout(title_font=dict(color="#40E0D0"), xaxis_title_font=dict(color="#28A745"),
                            yaxis_title_font=dict(color="#40E0D0"))
st.plotly_chart(shares_outstanding_graph)

    # "Date": ["2014", "2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023"],
    # "Debt": debt,

tabs = ["Cash&Debt", "ROIC", "ROCE" ]
