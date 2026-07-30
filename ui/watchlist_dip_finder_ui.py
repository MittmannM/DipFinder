from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from repositories import stock_data_repository as repository
from services.dip_finder_service import (
    PERIOD_LABELS,
    calculate_52_week_metrics,
    calculate_period_returns,
    determine_dip_status,
)
from services.valuation_service import calculate_valuation_percentile


def _empty_price_history():
    return pd.DataFrame(columns=["Adjusted Close"])


def _load_ticker_data(ticker):
    errors = []
    try:
        price_history = repository.get_price_history(ticker)
    except Exception as exc:
        price_history = _empty_price_history()
        errors.append(f"Kurse: {exc}")

    try:
        fundamentals = repository.get_fundamental_history(ticker)
    except Exception as exc:
        fundamentals = {
            "current_pe": None,
            "pe_history": pd.Series(dtype="float64", name="P/E"),
            "current_pfcf": None,
            "pfcf_history": pd.Series(dtype="float64", name="P/FCF"),
        }
        errors.append(f"Bewertung: {exc}")

    period_returns = calculate_period_returns(price_history)
    range_metrics = calculate_52_week_metrics(price_history)
    current_price = (
        float(price_history["Adjusted Close"].iloc[-1])
        if not price_history.empty
        else None
    )
    pe_percentile = calculate_valuation_percentile(
        fundamentals["current_pe"], fundamentals["pe_history"]
    )
    pfcf_percentile = calculate_valuation_percentile(
        fundamentals["current_pfcf"], fundamentals["pfcf_history"]
    )

    metrics = {
        "ticker": ticker,
        "current_price": current_price,
        "price_date": price_history.index[-1] if not price_history.empty else None,
        "updated_at": datetime.now().astimezone(),
        "period_returns": period_returns,
        **range_metrics,
        "current_pe": fundamentals["current_pe"],
        "pe_percentile": pe_percentile,
        "current_pfcf": fundamentals["current_pfcf"],
        "pfcf_percentile": pfcf_percentile,
        "errors": errors,
    }
    metrics["status"] = determine_dip_status(metrics)
    return metrics


def _summary_frame(results, selected_period):
    rows = []
    for metrics in results:
        rows.append(
            {
                "Ticker": metrics["ticker"],
                "Current Price": metrics["current_price"],
                "Selected Period Performance": metrics["period_returns"].get(selected_period),
                "52W Drawdown": metrics["drawdown_52w"],
                "52W Range Position": metrics["range_position_52w"],
                "Current P/E": metrics["current_pe"],
                "P/E Percentile": metrics["pe_percentile"],
                "Current P/FCF": metrics["current_pfcf"],
                "P/FCF Percentile": metrics["pfcf_percentile"],
                "Status": metrics["status"],
            }
        )
    return pd.DataFrame(rows)


def _render_performance_chart(summary, selected_period):
    chart_data = summary.dropna(subset=["Selected Period Performance"]).copy()
    if chart_data.empty:
        st.info(f"Für {selected_period} sind keine Performance-Daten verfügbar.")
        return

    chart_data["Performance"] = chart_data["Selected Period Performance"] * 100
    chart_data["Direction"] = chart_data["Performance"].map(
        lambda value: "Negative" if value < 0 else "Positive"
    )
    chart_data = chart_data.sort_values("Performance", ascending=True)

    figure = px.bar(
        chart_data,
        x="Performance",
        y="Ticker",
        orientation="h",
        color="Direction",
        color_discrete_map={"Negative": "#C44536", "Positive": "#26845B"},
        text="Performance",
        labels={"Performance": f"{selected_period} Performance (%)"},
    )
    figure.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    figure.update_layout(
        showlegend=False,
        height=max(320, 48 * len(chart_data) + 100),
        margin=dict(l=20, r=55, t=20, b=45),
        yaxis=dict(
            categoryorder="array",
            categoryarray=chart_data["Ticker"].tolist(),
            autorange="reversed",
        ),
    )
    figure.add_vline(x=0, line_width=1, line_color="#7B8491")
    st.plotly_chart(
        figure,
        key="dip_performance_chart",
        config={"displayModeBar": False},
    )


def _render_results_table(summary):
    display = summary.copy()
    percent_columns = [
        "Selected Period Performance",
        "52W Drawdown",
        "52W Range Position",
        "P/E Percentile",
        "P/FCF Percentile",
    ]
    for column in percent_columns:
        display[column] = display[column] * 100

    st.dataframe(
        display,
        hide_index=True,
        column_config={
            "Current Price": st.column_config.NumberColumn(format="%.2f"),
            "Selected Period Performance": st.column_config.NumberColumn(format="%.1f%%"),
            "52W Drawdown": st.column_config.NumberColumn(format="%.1f%%"),
            "52W Range Position": st.column_config.ProgressColumn(
                format="%.1f%%", min_value=0, max_value=100
            ),
            "Current P/E": st.column_config.NumberColumn(format="%.2f"),
            "P/E Percentile": st.column_config.NumberColumn(format="%.0f%%"),
            "Current P/FCF": st.column_config.NumberColumn(format="%.2f"),
            "P/FCF Percentile": st.column_config.NumberColumn(format="%.0f%%"),
        },
    )


def _render_status_explanation():
    with st.expander("Wie wird der Dip-Status bestimmt?"):
        st.markdown(
            """
- **Dip-Bedingung:** Die 1-Monats-Performance liegt bei höchstens **-8 %** oder der Abstand zum 52-Wochen-Hoch bei höchstens **-20 %**.
- **ATTRACTIVE_DIP:** Dip-Bedingung erfüllt und mindestens eines der beiden Bewertungsperzentile (KGV oder P/FCF) liegt bei höchstens **35 %**.
- **DIP:** Dip-Bedingung erfüllt und die Bewertung liegt weder im günstigen noch vollständig im teuren Bereich.
- **DIP_BUT_EXPENSIVE:** Dip-Bedingung erfüllt, aber KGV- und P/FCF-Perzentil liegen beide über **65 %**.
- **NO_DIP:** Weder die 1-Monats- noch die 52-Wochen-Dip-Schwelle ist erreicht.
- **INSUFFICIENT_DATA:** Kursdaten oder eines der benötigten Bewertungsperzentile fehlen.

Ein niedriges Bewertungsperzentil bedeutet, dass die Aktie im Vergleich zu ihrer eigenen Fünfjahreshistorie günstig bewertet ist.
            """
        )


def render_watchlist_dip_finder(watchlist):
    if not watchlist:
        st.info("Füge zuerst mindestens einen Ticker zur Watchlist hinzu.")
        return

    header_column, refresh_column = st.columns([5, 1], vertical_alignment="bottom")
    header_column.markdown("## Dip Finder")
    if refresh_column.button("Refresh Data", use_container_width=True, key="dip_refresh"):
        repository.clear_watchlist_caches()
        st.rerun()

    selected_period = st.segmented_control(
        "Zeitraum",
        options=list(PERIOD_LABELS),
        default="1M",
        key="dip_selected_period",
    ) or "1M"

    with st.spinner(f"Lade Dip-Daten für {len(watchlist)} Watchlist-Ticker..."):
        results = [_load_ticker_data(entry["ticker"]) for entry in watchlist]

    updated_at = max(metrics["updated_at"] for metrics in results)
    price_dates = [metrics["price_date"] for metrics in results if metrics["price_date"] is not None]
    latest_price_date = max(price_dates) if price_dates else None
    update_text = updated_at.strftime("%d.%m.%Y, %H:%M:%S %Z")
    if latest_price_date is not None:
        update_text += f" | Letzter Handelstag: {latest_price_date:%d.%m.%Y}"
    st.caption(f"Zuletzt aktualisiert: {update_text}")
    _render_status_explanation()

    failed = [metrics for metrics in results if metrics["errors"]]
    if failed:
        with st.expander(f"Datenfehler ({len(failed)})"):
            for metrics in failed:
                st.warning(f"{metrics['ticker']}: {'; '.join(metrics['errors'])}")

    summary = _summary_frame(results, selected_period)
    _render_performance_chart(summary, selected_period)

    st.markdown("### Ergebnisse")
    _render_results_table(summary)
