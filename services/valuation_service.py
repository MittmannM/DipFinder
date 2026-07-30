import math

import pandas as pd


def _positive_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def calculate_valuation_percentile(current_value, history):
    current = _positive_number(current_value)
    if current is None:
        return None

    values = pd.to_numeric(pd.Series(history, dtype="object"), errors="coerce")
    values = values[values.map(lambda value: _positive_number(value) is not None)]
    if values.empty:
        return None

    return float((values < current).sum() / len(values))
