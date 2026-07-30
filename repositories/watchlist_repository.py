import json
from pathlib import Path
import re


WATCHLIST_PATH = Path(__file__).resolve().parents[1] / "watchlist.json"


def normalize_ticker(value):
    ticker = str(value).strip().upper()
    if not ticker or not re.fullmatch(r"[A-Z0-9^=._:-]+", ticker):
        return None
    return ticker


def load_watchlist():
    if not WATCHLIST_PATH.exists():
        return []
    try:
        data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []

    entries = []
    seen_tickers = set()
    for item in data:
        if isinstance(item, dict):
            ticker = normalize_ticker(item.get("ticker", ""))
            raw_name = item.get("name")
            name = str(raw_name).strip() if raw_name else None
        else:
            ticker = normalize_ticker(item)
            name = None
        if ticker and ticker not in seen_tickers:
            entries.append({"ticker": ticker, "name": name})
            seen_tickers.add(ticker)
    return entries


def save_watchlist(entries):
    temporary_path = WATCHLIST_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    temporary_path.replace(WATCHLIST_PATH)
