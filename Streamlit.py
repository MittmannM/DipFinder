import os
from datetime import datetime, timedelta
import requests
import streamlit as st, pandas as pd, yfinance as yf
import plotly.express as px

#TODO 2: Custom Zeiträume erlauben statt immer 10 Jahre
#TODO 4: Historische ROIC und ROCE wachstumsraten berechnen + graphen
#TODO 5: Sidebar ausprobieren (metrics und ticker eingabe)
#TODO 6: Aktuellen Stockprice anzeigen
#TODO 7: Quartalsanzeige

BASE_URL = "https://public-api.quickfs.net/v1/data/batch"

headers = {
    "x-qfs-api-key": os.getenv('QUICKFS_API_KEY')
}

API_KEY = os.getenv("ALPHA_VANTAGE_KEY")


st.title("Stock Tool")

ticker = st.sidebar.text_input("Enter stock ticker:", "V")
input_years = st.sidebar.selectbox("Select number of years to look at:", options=[10, 15, 20])


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
def get_graph_data_from_quickfs(ticker, years):
    # Adjust for the last index (e.g. 10 years -> we go from year 2023 to 2014)
    years = years - 1
    # Construct the request body with the required metrics and periods
    request_body = {
        "data": {
            "revenue": {ticker: f"QFS({ticker}:US,revenue,FY-{years}:FY)"},
            "revenue_growth": {ticker: f"QFS({ticker}:US,revenue_growth,FY-{years}:FY)"},
            "fcf": {ticker: f"QFS({ticker}:US,fcf,FY-{years}:FY)"},
            "fcf_growth": {ticker: f"QFS({ticker}:US,fcf_growth,FY-{years}:FY)"},
            "net_debt": {ticker: f"QFS({ticker}:US,net_debt,FY-{years}:FY)"},
            "eps_diluted": {ticker: f"QFS({ticker}:US,eps_diluted,FY-{years}:FY)"},
            "eps_diluted_growth": {ticker: f"QFS({ticker}:US,eps_diluted_growth,FY-{years}:FY)"},
            "dividends": {ticker: f"QFS({ticker}:US,dividends,FY-{years}:FY)"},
            "dividends_per_share_growth": {ticker: f"QFS({ticker}:US,dividends_per_share_growth,FY-{years}:FY)"},
            "net_income": {ticker: f"QFS({ticker}:US,net_income,FY-{years}:FY)"},
            "net_income_growth": {ticker: f"QFS({ticker}:US,net_income_growth,FY-{years}:FY)"},
            "ebitda": {ticker: f"QFS({ticker}:US,ebitda,FY-{years}:FY)"},
            "ebitda_growth": {ticker: f"QFS({ticker}:US,ebitda_growth,FY-{years}:FY)"},
            "shares_diluted": {ticker: f"QFS({ticker}:US,shares_diluted,FY-{years}:FY)"},
            "shares_diluted_growth": {ticker: f"QFS({ticker}:US,shares_diluted_growth,FY-{years}:FY)"},
            "roce": {ticker: f"QFS({ticker}:US,roce,FY-{years}:FY)"},
            "roic": {ticker: f"QFS({ticker}:US,roic,FY-{years}:FY)"}
        }
    }

    # Make the POST request to the API
    response = requests.post(BASE_URL, json=request_body, headers=headers)
    print(response.json())

    data = response.json()["data"]

    year_rn = datetime.now().year

    year_list = list(range(year_rn - (years + 1), year_rn))

    financial_data = {
        "Date": year_list,
        "Revenue": data["revenue"][ticker],
        "Revenue Growth": data["revenue_growth"][ticker],
        "Free Cash Flow": data["fcf"][ticker],
        "Free Cash Flow Growth": data["fcf_growth"][ticker],
        "Net Debt": data["net_debt"][ticker],
        "EPS Diluted": data["eps_diluted"][ticker],
        "EPS Diluted Growth": data["eps_diluted_growth"][ticker],
        "Dividends": data["dividends"][ticker],
        "Dividends PS Growth": data["dividends_per_share_growth"][ticker],
        "Net Income": data["net_income"][ticker],
        "Net Income Growth": data["net_income_growth"][ticker],
        "EBITDA": data["ebitda"][ticker],
        "EBITDA Growth": data["ebitda_growth"][ticker],
        "Shares Outstanding": data["shares_diluted"][ticker],
        "Shares Outstanding Growth": data["shares_diluted_growth"][ticker],
        "ROCE": data["roce"][ticker],
        "ROIC": data["roic"][ticker],
    }

    df = pd.DataFrame(financial_data)
    return df


@st.cache_data
def calc_avg_growth_rates(growth_list):

    func = lambda x: round(sum(growth_list[len(growth_list)-x::]) / x * 100, 2)

    return func(1), func(2), func(5), func(10)


@st.cache_data
def calc_yoy_growth_rates(input_list):

    growth_list = []

    for i in range(0, len(input_list) - 1):
        growth_value = (input_list[i+1] - input_list[i]) / abs(input_list[i])
        growth_list.append(growth_value)

    return growth_list


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

df = get_graph_data_from_quickfs(ticker, input_years)


one_year, two_year, five_year, ten_year = calc_avg_growth_rates(df["Revenue Growth"].tolist())
revenue_graph = px.bar(df, x=df["Date"], y=df["Revenue"], title="Revenue (USD)", color_discrete_sequence=["#CC8124"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
revenue_graph.update_layout(title_font=dict(color="#CC8124"), xaxis_title_font=dict(color="#2B824C"),
                            yaxis_title_font=dict(color="#CC8124"))
st.plotly_chart(revenue_graph)


one_year, two_year, five_year, ten_year = calc_avg_growth_rates(df["EBITDA Growth"].tolist())
ebitda_graph = px.bar(df, x=df["Date"], y=df["EBITDA"], title="EBITDA (USD)", color_discrete_sequence=["#71BACB"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
ebitda_graph.update_layout(title_font=dict(color="#71BACB"), xaxis_title_font=dict(color="#2B824C"),
                            yaxis_title_font=dict(color="#71BACB"))
st.plotly_chart(ebitda_graph)


one_year, two_year, five_year, ten_year = calc_avg_growth_rates(df["Free Cash Flow Growth"].tolist())
free_cashflow_graph = px.bar(df, x=df["Date"], y=df["Free Cash Flow"], title="Free Cash Flow (USD)", color_discrete_sequence=["#2EBD2E"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
free_cashflow_graph.update_layout(title_font=dict(color="#2EBD2E"), xaxis_title_font=dict(color="#2B824C"),
                            yaxis_title_font=dict(color="#2EBD2E"))
st.plotly_chart(free_cashflow_graph)


one_year, two_year, five_year, ten_year = calc_avg_growth_rates(df["Net Income Growth"].tolist())
net_income_graph = px.bar(df, x=df["Date"], y=df["Net Income"], title="Net Income (USD)", color_discrete_sequence=["#BB9E81"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
net_income_graph.update_layout(title_font=dict(color="#BB9E81"), xaxis_title_font=dict(color="#2B824C"),
                            yaxis_title_font=dict(color="#BB9E81"))
st.plotly_chart(net_income_graph)


one_year, two_year, five_year, ten_year = calc_avg_growth_rates(df["EPS Diluted Growth"].tolist())
eps_graph = px.bar(df, x=df["Date"], y=df["EPS Diluted"], title="EPS Diluted (USD)", color_discrete_sequence=["#C0B607"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
eps_graph.update_layout(title_font=dict(color="#C0B607"), xaxis_title_font=dict(color="#2B824C"),
                            yaxis_title_font=dict(color="#C0B607"))
st.plotly_chart(eps_graph)


one_year, two_year, five_year, ten_year = calc_avg_growth_rates(df["Dividends PS Growth"].tolist())
dividends_graph = px.bar(df, x=df["Date"], y=df["Dividends"], title="Dividends (USD)", color_discrete_sequence=["#22673D"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
dividends_graph.update_layout(title_font=dict(color="#22673D"), xaxis_title_font=dict(color="#2B824C"),
                            yaxis_title_font=dict(color="#22673D"))
st.plotly_chart(dividends_graph)


debt_growth_list = calc_yoy_growth_rates(df["Net Debt"])
one_year, two_year, five_year, ten_year = calc_avg_growth_rates(debt_growth_list)
debt_graph = px.bar(df, x=df["Date"], y=df["Net Debt"], title=" Net Debt", color_discrete_sequence=["#C40824"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
debt_graph.update_layout(title_font=dict(color="#C40824"), xaxis_title_font=dict(color="#2B824C"),
                            yaxis_title_font=dict(color="#C40824"))
st.plotly_chart(debt_graph)


roic_growth_list = calc_yoy_growth_rates(df["ROIC"])
one_year, two_year, five_year, ten_year = calc_avg_growth_rates(roic_growth_list)
roic_graph = px.bar(df, x=df["Date"], y=df["ROIC"], title="ROIC", color_discrete_sequence=["#4682B4"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
roic_graph.update_layout(title_font=dict(color="#4682B4"), xaxis_title_font=dict(color="#2B824C"),
                            yaxis_title_font=dict(color="#4682B4"))
st.plotly_chart(roic_graph)


roce_growth_list = calc_yoy_growth_rates(df["ROCE"])
one_year, two_year, five_year, ten_year = calc_avg_growth_rates(roce_growth_list)
roce_graph = px.bar(df, x=df["Date"], y=df["ROCE"], title="ROCE", color_discrete_sequence=["#896263"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
roce_graph.update_layout(title_font=dict(color="#896263"), xaxis_title_font=dict(color="#2B824C"),
                            yaxis_title_font=dict(color="#896263"))
st.plotly_chart(roce_graph)


one_year, two_year, five_year, ten_year = calc_avg_growth_rates(df["Shares Outstanding Growth"].tolist())
shares_outstanding_graph = px.bar(df, x=df["Date"], y=df["Shares Outstanding"], title="Shares Outstanding", color_discrete_sequence=["#15A1B1"],
                           labels={"Date": f"1Y: {one_year}% 2Y: {two_year}% 5Y: {five_year}% 10Y: {ten_year}%"})
shares_outstanding_graph.update_layout(title_font=dict(color="#15A1B1"), xaxis_title_font=dict(color="#2B824C"),
                            yaxis_title_font=dict(color="#15A1B1"))
st.plotly_chart(shares_outstanding_graph)

