from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from repositories import stock_data_repository as repository
from services.dcf_calculator_service import (
    FORECAST_YEARS,
    calculate_dcf_projection,
    calculate_dcf_scenario,
)
from ui.fundamental_data_ui import load_fundamental_history


def _value_or_default(value, default, minimum, maximum):
    if value is None or pd.isna(value):
        return default
    return round(min(max(float(value), minimum), maximum), 2)


def _money(value, currency):
    if value is None or pd.isna(value):
        return "N/A"
    suffix = f" {currency}" if currency else ""
    return f"{value:,.2f}{suffix}"


def _percent(value, digits=1):
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value * 100:.{digits}f}%"


def _render_instructions():
    with st.expander("Anleitung"):
        st.markdown(
            """
- **Earnings oder Cash Flow wählen:** Die aktuellen TTM-Werte und die verfügbare Wachstumsrate werden automatisch geladen.
- **Wachstumsrate anpassen:** Erwartetes jährliches EPS- beziehungsweise FCF-je-Aktie-Wachstum für fünf Jahre.
- **Endbewertung festlegen:** Angemessenes KGV oder angemessene FCF-Rendite im fünften Jahr.
- **Gewünschte Rendite eingeben:** Daraus wird der maximal vertretbare Einstiegspreis berechnet.
            """
        )


def _projection_chart(projection, currency):
    data = pd.DataFrame(projection)
    current_year = datetime.now().year
    data["Calendar Year"] = data["year"].map(lambda year: current_year + year)

    figure = go.Figure(
        go.Scatter(
            x=data["Calendar Year"],
            y=data["projected_price"],
            mode="lines+markers",
            line=dict(color="#2E8B67", width=3),
            marker=dict(color="#2E8B67", size=9),
            customdata=data[["metric_per_share", "valuation_assumption"]],
            hovertemplate=(
                "<b>%{x}</b><br>Projected Price: %{y:,.2f}"
                + (f" {currency}" if currency else "")
                + "<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title="5-Year Price Projection",
        showlegend=False,
        height=480,
        margin=dict(l=25, r=25, t=55, b=35),
        xaxis=dict(dtick=1, title=None),
        yaxis=dict(title=currency or "Price", tickformat=",.0f"),
    )
    return figure


def render_dcf_calculator(ticker, markets_sh_token):
    header_column, refresh_column = st.columns([5, 1], vertical_alignment="bottom")
    header_column.title("DCF Calculator")
    if refresh_column.button("Refresh Data", key="dcf_refresh", use_container_width=True):
        repository.clear_dcf_cache()
        st.rerun()

    _render_instructions()
    fundamental_history = load_fundamental_history(ticker, markets_sh_token)

    with st.spinner(f"Lade TTM-Daten für {ticker.upper()}..."):
        try:
            inputs = repository.get_dcf_calculator_inputs(ticker, fundamental_history)
        except Exception as exc:
            st.error(f"DCF-Daten für {ticker.upper()} konnten nicht geladen werden: {exc}")
            return

    company_column, price_column = st.columns([5, 1], vertical_alignment="center")
    company_column.subheader(f"{inputs['name']} ({inputs['ticker']})")
    price_column.metric(
        "Current Price",
        _money(inputs["current_price"], inputs["currency"]),
    )
    basis_label = st.segmented_control(
        "Valuation Basis",
        options=["Earnings", "Cash Flow"],
        default="Earnings",
        key="dcf_basis",
    ) or "Earnings"
    basis = "EPS" if basis_label == "Earnings" else "FCF"

    if basis == "EPS":
        current_metric = inputs["trailing_eps"]
        current_assumption = inputs["trailing_pe"]
        loaded_growth = inputs["eps_growth"]
        section_title = "Current Earnings"
        metric_label = "EPS (TTM)"
        assumption_label = "PE (TTM)"
        growth_label = "EPS Growth"
        growth_source = inputs.get("eps_growth_source")
        historical_growth_5y = inputs.get("eps_growth_5y")
        historical_growth_10y = inputs.get("eps_growth_10y")
        historical_assumption_5y = inputs.get("pe_average_5y")
        historical_assumption_10y = inputs.get("pe_average_10y")
    else:
        current_metric = inputs["fcf_per_share"]
        current_assumption = inputs["current_fcf_yield"]
        loaded_growth = inputs["fcf_growth"]
        section_title = "Current Cash Flow"
        metric_label = "FCF/Share (TTM)"
        assumption_label = "FCF Yield (TTM)"
        growth_label = "FCF/Share Growth"
        growth_source = inputs.get("fcf_growth_source")
        historical_growth_5y = inputs.get("fcf_growth_5y")
        historical_growth_10y = inputs.get("fcf_growth_10y")
        historical_assumption_5y = inputs.get("fcf_yield_average_5y")
        historical_assumption_10y = inputs.get("fcf_yield_average_10y")

    if inputs["current_price"] is None or inputs["current_price"] <= 0:
        st.error("Der aktuelle Aktienkurs ist nicht verfügbar.")
        return
    if current_metric is None or current_metric <= 0:
        st.error(f"{metric_label} ist nicht positiv oder nicht verfügbar.")
        return
    if current_assumption is None or current_assumption <= 0:
        st.error(f"{assumption_label} ist nicht positiv oder nicht verfügbar.")
        return

    assumptions_summary, projection_summary = st.columns([1, 1.08], gap="large")

    with assumptions_summary:
        st.subheader("Assumptions")
        st.markdown(f"#### {section_title}")
        current_metric_column, current_assumption_column, growth_column = st.columns(3)
        current_metric_column.metric(metric_label, f"{current_metric:.2f}")
        if basis == "EPS":
            current_assumption_column.metric(assumption_label, f"{current_assumption:.2f}")
        else:
            current_assumption_column.metric(assumption_label, _percent(current_assumption))
        growth_column.metric(growth_label, _percent(loaded_growth))
        if growth_source:
            st.caption(f"Growth source: {growth_source}")

        st.markdown("**Growth references**")
        loaded_growth_column, growth_5y_column, growth_10y_column = st.columns(3)
        loaded_growth_column.metric(
            "Analyst (+1Y)" if basis == "EPS" else "Loaded Growth",
            _percent(loaded_growth),
        )
        growth_5y_column.metric("5Y Average", _percent(historical_growth_5y))
        growth_10y_column.metric("10Y Average", _percent(historical_growth_10y))

        st.markdown("**Valuation references**")
        current_value_column, value_5y_column, value_10y_column = st.columns(3)
        if basis == "EPS":
            current_value_column.metric("Current PE", f"{current_assumption:.2f}")
            value_5y_column.metric(
                "5Y Average PE",
                f"{historical_assumption_5y:.2f}" if historical_assumption_5y is not None else "N/A",
            )
            value_10y_column.metric(
                "10Y Average PE",
                f"{historical_assumption_10y:.2f}" if historical_assumption_10y is not None else "N/A",
            )
        else:
            current_value_column.metric("Current FCF Yield", _percent(current_assumption))
            value_5y_column.metric("5Y Average Yield", _percent(historical_assumption_5y))
            value_10y_column.metric("10Y Average Yield", _percent(historical_assumption_10y))

        if inputs.get("historical_source"):
            st.caption(
                f"Historical averages: {inputs['historical_source']}. "
                "Only positive annual values are included."
            )

    with projection_summary:
        st.subheader("5-Year Projection")
        st.markdown("#### Calculation Results")
        results_placeholder = st.empty()

    assumptions_column, projection_column = st.columns(
        [1, 1.08],
        gap="large",
        vertical_alignment="center",
    )

    with assumptions_column:
        st.number_input(
            metric_label,
            value=float(current_metric),
            disabled=True,
            format="%.2f",
            key=f"dcf_current_metric_{basis.lower()}",
            help="Der von Yahoo Finance geladene Wert der letzten zwölf Monate.",
        )
        growth_default = _value_or_default(
            loaded_growth * 100 if loaded_growth is not None else None,
            10.0,
            -99.0,
            100.0,
        )
        growth_percent = st.number_input(
            f"{growth_label} Rate (%)",
            min_value=-99.0,
            max_value=100.0,
            value=growth_default,
            step=0.5,
            key=f"dcf_growth_{basis.lower()}",
            help="Erwartetes jährliches Wachstum für die nächsten fünf Jahre.",
        )

        if basis == "EPS":
            terminal_default = _value_or_default(current_assumption, 20.0, 0.1, 200.0)
            terminal_assumption = st.number_input(
                "Appropriate EPS Multiple",
                min_value=0.1,
                max_value=200.0,
                value=terminal_default,
                step=0.5,
                key="dcf_terminal_eps",
                help="Das KGV, das du im fünften Jahr für angemessen hältst.",
            )
        else:
            terminal_default = _value_or_default(current_assumption * 100, 5.0, 0.1, 100.0)
            terminal_yield_percent = st.number_input(
                "Appropriate FCF Yield (%)",
                min_value=0.1,
                max_value=100.0,
                value=terminal_default,
                step=0.25,
                key="dcf_terminal_fcf",
                help="Die FCF-Rendite, die du im fünften Jahr für angemessen hältst.",
            )
            terminal_assumption = terminal_yield_percent / 100

        desired_return_percent = st.number_input(
            "Desired Return (%)",
            min_value=-99.0,
            max_value=100.0,
            value=15.0,
            step=0.5,
            key="dcf_desired_return",
            help="Deine angestrebte jährliche Rendite.",
        )

    result = calculate_dcf_scenario(
        current_price=inputs["current_price"],
        current_metric_per_share=current_metric,
        annual_growth_rate=growth_percent / 100,
        terminal_assumption=terminal_assumption,
        desired_annual_return=desired_return_percent / 100,
        basis=basis,
    )
    projection = calculate_dcf_projection(
        current_price=inputs["current_price"],
        current_metric_per_share=current_metric,
        annual_growth_rate=growth_percent / 100,
        current_assumption=current_assumption,
        terminal_assumption=terminal_assumption,
        basis=basis,
    )

    with results_placeholder.container():
        return_column, entry_column = st.columns(2)
        return_column.metric("Return from today's price", _percent(result["annual_return"], 2))
        entry_column.metric(
            f"Entry Price for {desired_return_percent:.1f}% Return",
            _money(result["maximum_purchase_price"], inputs["currency"]),
        )

    with projection_column:
        st.plotly_chart(
            _projection_chart(projection, inputs["currency"]),
            key=f"dcf_projection_{basis.lower()}",
            config={"displayModeBar": False},
        )
        st.caption(
            f"Year {FORECAST_YEARS} projected price: {_money(result['future_price'], inputs['currency'])} | "
            f"Total return: {_percent(result['total_return'])} | Multiple: {result['multiple']:.2f}x"
        )

    st.caption(
        f"TTM-Daten geladen: {inputs['updated_at']:%d.%m.%Y, %H:%M:%S %Z}. "
        "Die Projektion enthält keine Dividenden und unterstellt konstantes Wachstum."
    )
