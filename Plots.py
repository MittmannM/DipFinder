import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import numpy as np
import StockAnalysis as SA


class StockApp(tk.Tk):
    ticker = ""

    def __init__(self):
        super().__init__()
        self.title("Stock Data Dashboard")
        self.geometry("1920x1080")

        # Create a frame for the input field and button
        self.input_frame = ttk.Frame(self)
        self.input_frame.pack(side='top', fill='x', padx=10, pady=5)

        # Define larger font size
        self.large_font = ('Helvetica', 12)

        # Create and add the label for the input field
        self.ticker_label = tk.Label(self.input_frame, text="Ticker:", font=self.large_font)
        self.ticker_label.grid(row=0, column=0, padx=5, pady=5, sticky='w')

        # Create and add the input field
        self.ticker_entry = tk.Entry(self.input_frame, font=self.large_font)
        self.ticker_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        # Create and add the update button
        self.update_button = tk.Button(self.input_frame, text="Update", command=self.update_data, font=self.large_font)
        self.update_button.grid(row=0, column=2, padx=5, pady=5)

        # Create a notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True)

        # Create frames for each section
        self.home_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.home_frame, text=f"{self.ticker}")

        # Create an area for expanded graphs
        self.expanded_frame = ttk.Frame(self)
        self.expanded_frame.pack(fill='both', expand=True)

    def create_thumbnails(self, df):
        # Create revenue thumbnail
        self.create_thumbnail('Revenue', df['Date'], df['Revenue'], 1, 0, df)
        # Create free cash flow thumbnail
        self.create_thumbnail('Free Cash Flow', df['Date'], df['Free Cash Flow'], 1, 2, df)
        # Create debt thumbnail
        self.create_thumbnail('EPS Diluted', df['Date'], df['EPS Diluted'], 1, 1, df)

        self.create_thumbnail('Debt', df['Date'], df['Debt'], 3, 5, df)

        self.create_thumbnail('Dividends', df['Date'], df['Dividends'], 1, 5, df)

        self.create_thumbnail('Dividends PS Growth', df['Date'], df['Dividends PS Growth'], 2, 5, df)

        self.create_thumbnail('Revenue Growth', df['Date'], df['Revenue Growth'], 2, 0, df)

        self.create_thumbnail('EPS Diluted Growth', df['Date'], df['EPS Diluted Growth'], 2, 1, df)

        self.create_thumbnail('Free Cash Flow Growth', df['Date'], df['Free Cash Flow Growth'], 2, 2, df)

    def create_thumbnail(self, name, x, y, row, column, df):
        fig = Figure(figsize=(3, 2), dpi=100)
        ax = fig.add_subplot(111)
        ax.bar(x, y, width=0.9, align='center')
        ax.set_title(name)

        # Adjust the x-axis to show only every second year
        ax.set_xticks(x[::2])

        canvas = FigureCanvasTkAgg(fig, master=self.home_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.grid(row=row, column=column, padx=5, pady=5)

        canvas_widget.bind("<Button-1>", lambda event, title=name: self.expand_graph(name, df))

    def expand_graph(self, title, df):
        # Create a new top-level window for the expanded graph
        expanded_window = tk.Toplevel(self)
        expanded_window.attributes('-fullscreen', True)  # Make the new window fullscreen

        # Add a close button to exit fullscreen
        close_button = tk.Button(expanded_window, text="Close", command=expanded_window.destroy, bg='red', fg='white')
        close_button.pack(side='top', anchor='ne')

        # Create and display the expanded graph
        fig = Figure(figsize=(expanded_window.winfo_screenwidth() / 100, expanded_window.winfo_screenheight() / 100),
                     dpi=100)
        ax = fig.add_subplot(111)
        if title == 'Revenue':
            ax.bar(df['Date'], df['Revenue'])
            ax.set_title('Revenue')
        elif title == 'Free Cash Flow':
            ax.bar(df['Date'], df['Free Cash Flow'])
            ax.set_title('Free Cash Flow')
        elif title == 'EPS Diluted':
            ax.bar(df['Date'], df['EPS Diluted'])
            ax.set_title('EPS Diluted')
        elif title == 'Dividends':
            ax.bar(df['Date'], df['Dividends'])
            ax.set_title('Dividends')
        elif title == 'Debt':
            ax.bar(df['Date'], df['Debt'])
            ax.set_title('Debt')
        elif title == 'Debt':
            ax.bar(df['Date'], df['Revenue Growth'])
            ax.set_title('Revenue Growth')
        elif title == 'Debt':
            ax.bar(df['Date'], df['EPS Diluted Growth'])
            ax.set_title('EPS Diluted Growth')
        elif title == 'Debt':
            ax.bar(df['Date'], df['Free Cash Flow Growth'])
            ax.set_title('Free Cash Flow Growth')
        elif title == 'Debt':
            ax.bar(df['Date'], df['Dividends PS Growth'])
            ax.set_title('Dividend Growth')

        # Create a canvas and add the plot to the new window
        canvas = FigureCanvasTkAgg(fig, master=expanded_window)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill='both', expand=True)

        # Update the new window to ensure it is displayed correctly
        expanded_window.update()

    def plot_expanded_graph(self, x, y, title):
        fig = Figure(figsize=(6, 4), dpi=100)
        ax = fig.add_subplot(111)
        ax.bar(x, y, width=100, align='center')
        ax.set_title(title)

        canvas = FigureCanvasTkAgg(fig, master=self.expanded_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill='both', expand=True)

    def update_data(self):
        self.ticker = self.ticker_entry.get()

        revenue = SA.call_api_single(self.ticker, "revenue", 10)["data"]
        revenue_growth = SA.call_api_single(self.ticker, "revenue_growth", 10)["data"]
        fcf = SA.call_api_single(self.ticker, "fcf", 10)["data"]
        fcf_growth = SA.call_api_single(self.ticker, "fcf_growth", 10)["data"]
        debt = SA.call_api_single(self.ticker, "st_debt", 10)["data"]
        eps_diluted = SA.call_api_single(self.ticker, "eps_diluted", 10)["data"]
        eps_diluted_growth = SA.call_api_single(self.ticker, "eps_diluted_growth", 10)["data"]
        dividends = SA.call_api_single(self.ticker, "dividends", 10)["data"]
        dividends_ps_growth = SA.call_api_single(self.ticker, "dividends_per_share_growth", 10)["data"]

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
        }

        df = pd.DataFrame(data)

        print(f"Updating data for ticker: {self.ticker}")
        self.create_thumbnails(df)
        self.notebook.add(self.home_frame, text=f"{self.ticker}")


if __name__ == "__main__":
    app = StockApp()
    app.mainloop()
