import pandas as pd
import tkinter as tk
import yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

my_tickers_path = "MyStocks.xlsx"


# read in my stock tickers
def read_in_tickers():
    df = pd.read_excel(my_tickers_path)

    return df.iloc[:, 0].tolist()


def calc_sma(ticker):
    data = yf.download(ticker, period="2y")

    sma_30 = data["Close"].rolling(window=30).mean().iloc[-1]
    sma_200 = data["Close"].rolling(window=200).mean().iloc[-1]
    sma_300 = data["Close"].rolling(window=300).mean().iloc[-1]
    price = data["Close"].iloc[-1]

    return price, sma_30, sma_200, sma_300


def calc_fcf_and_yield(ticker):
    stock_ticker = yf.Ticker(ticker)

    fcf = stock_ticker.cashflow.loc["Free Cash Flow"].iloc[0]

    shares = stock_ticker.info.get("sharesOutstanding", None)

    market_cap = stock_ticker.info.get("marketCap", None)

    fcf_per_share = fcf / shares
    fcf_yield = (fcf / market_cap) * 100

    return fcf_per_share, fcf_yield


def calc_market_cap_and_fcf_history(ticker, years):
    market_cap_history = []

    stock_ticker = yf.Ticker(ticker)

    fcf_history = stock_ticker.cashflow.loc['Free Cash Flow'].iloc[:3]

    for years in stock_ticker.cashflow.columns[:years]:

        price = stock_ticker.history(period='1d', start=pd.Timestamp(years) - pd.DateOffset(days=7),
                                     end=pd.Timestamp(years) + pd.DateOffset(days=7))['Close'].iloc[-1]

        shares_outstanding_series = stock_ticker.get_shares_full(start=pd.Timestamp(years) - pd.DateOffset(days=60),
                                                                 end=pd.Timestamp(years) + pd.DateOffset(days=60))

        shares_outstanding = int(shares_outstanding_series.array[0])

        market_cap_history.append(price * shares_outstanding)

    return market_cap_history, fcf_history


def calc_mean_fcf_yield(fcf_history, market_cap_history):
    historical_fcf_yields = []
    for fcf, mc in zip(fcf_history, market_cap_history):
        historical_fcf_yields.append((fcf / mc) * 100)
    mean_fcf_yield = sum(historical_fcf_yields) / len(historical_fcf_yields)

    return mean_fcf_yield


def get_stock_info_from_api(tickers, dip_df):
    for ticker in tickers:

        try:
            price, sma_30, sma_200, sma_300 = calc_sma(ticker)

            fcf_per_share, fcf_yield = calc_fcf_and_yield(ticker)

            market_cap_history, fcf_history = calc_market_cap_and_fcf_history(ticker, 3)

            mean_fcf_yield = calc_mean_fcf_yield(fcf_history, market_cap_history)

            dip_df.loc[len(dip_df.index)] = [ticker, price, sma_30, sma_200, sma_300, fcf_per_share, fcf_yield,
                                             mean_fcf_yield]

        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")

    return dip_df


# read in tickers of my stocks
my_tickers = read_in_tickers()

stock_df = pd.DataFrame(
    columns=["Ticker", "Price", "30-Day SMA", "200-Day SMA", "300-Day SMA", "FCF-per-Share", "FCF-yield",
             "3y mean FCF-yield"])

stock_df = get_stock_info_from_api(my_tickers, stock_df)

# Calculate percentage differences
stock_df["30-Day Diff (%)"] = ((stock_df["Price"] - stock_df["30-Day SMA"]) / stock_df["30-Day SMA"]) * 100
stock_df["200-Day Diff (%)"] = ((stock_df["Price"] - stock_df["200-Day SMA"]) / stock_df["200-Day SMA"]) * 100
stock_df["300-Day Diff (%)"] = ((stock_df["Price"] - stock_df["300-Day SMA"]) / stock_df["300-Day SMA"]) * 100

stock_df["FCF-yield Diff (%)"] = stock_df["FCF-yield"] - stock_df["3y mean FCF-yield"]


# Function to create bar charts
def create_bar_chart(data, title, ylabel):
    fig, ax = plt.subplots()
    data_sorted = data.sort_values()
    ax.bar(data_sorted.index, data_sorted.values)
    ax.set_xlabel('Ticker')
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(range(len(data_sorted.index)))
    ax.set_xticklabels(data_sorted.index, rotation=45)
    return fig


# Functions to plot different graphs
def plot_30_day_sma():
    fig = create_bar_chart(stock_df.set_index("Ticker")["30-Day Diff (%)"], "30-Day SMA vs Current Price",
                           "Difference (%)")
    display_plot(fig)


def plot_200_day_sma():
    fig = create_bar_chart(stock_df.set_index("Ticker")["200-Day Diff (%)"], "200-Day SMA vs Current Price",
                           "Difference (%)")
    display_plot(fig)


def plot_300_day_sma():
    fig = create_bar_chart(stock_df.set_index("Ticker")["300-Day Diff (%)"], "300-Day SMA vs Current Price",
                           "Difference (%)")
    display_plot(fig)


# Function to plot free cash flow yield
def plot_fcf_yield():
    fig = create_bar_chart(stock_df.set_index("Ticker")["FCF-yield"], "Free Cash Flow Yield", "FCF Yield (%)")
    display_plot(fig)


# Function to display plot in tkinter window
def plot_fcf_yield_diff():
    fig = create_bar_chart(stock_df.set_index("Ticker")["FCF-yield Diff (%)"], "FCF Yield Difference (Now vs 3Y Mean)",
                           "Difference")
    display_plot(fig)


def display_plot(fig):
    for widget in plot_frame.winfo_children():
        widget.destroy()
    canvas = FigureCanvasTkAgg(fig, master=plot_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)


# Create the main application window
root = tk.Tk()
root.title("Stock Analysis")

root.attributes('-fullscreen', True)

# Create frames
button_frame = tk.Frame(root)
button_frame.pack(side=tk.RIGHT, fill=tk.Y)
plot_frame = tk.Frame(root)
plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

# Create exit button
exit_button = tk.Button(button_frame, text="Exit", command=root.quit)
exit_button.pack(padx=10, pady=10)

# Create buttons for SMA
button_30_day_sma = tk.Button(button_frame, text="30-Day SMA", command=plot_30_day_sma)
button_30_day_sma.pack(padx=10, pady=10)

button_200_day_sma = tk.Button(button_frame, text="200-Day SMA", command=plot_200_day_sma)
button_200_day_sma.pack(padx=10, pady=10)

button_300_day_sma = tk.Button(button_frame, text="300-Day SMA", command=plot_300_day_sma)
button_300_day_sma.pack(padx=10, pady=10)

# Create button for FCF Yield
button_fcf_yield = tk.Button(button_frame, text="FCF Yield", command=plot_fcf_yield)
button_fcf_yield.pack(padx=10, pady=10)

# Create button for FCF Yield Difference graph
button_fcf_yield_diff = tk.Button(button_frame, text="3y mean fcf diff to now", command=plot_fcf_yield_diff)
button_fcf_yield_diff.pack(padx=10, pady=10)

# Start the Tkinter main loop
root.mainloop()
