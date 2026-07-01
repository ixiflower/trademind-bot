"""Market Data Fetcher"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from config import AVAILABLE_PAIRS

# ---- Proxy-bypass session for all API calls ----
_session = requests.Session()
_session.proxies = {"http": "", "https": ""}  # no proxy
_session.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json"})

# ---- Binance ----
BINANCE_BASE = "https://api.binance.com"


def _binance_klines(symbol: str, interval: str, limit: int = 100) -> list | None:
    url = f"{BINANCE_BASE}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        resp = _session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[Binance] Error fetching {symbol}: {e}")
        return None


def binance_to_dataframe(raw: list) -> pd.DataFrame | None:
    if not raw:
        return None
    df = pd.DataFrame(raw, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades", "taker_buy_vol",
        "taker_buy_quote_vol", "ignore"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df


# ---- Yahoo Finance ----
YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"


def _fetch_yahoo_csv(symbol: str, interval: str = "5m") -> pd.DataFrame | None:
    url = f"{YAHOO_BASE}/{symbol}"
    params = {
        "symbol": symbol,
        "period1": int((datetime.now(timezone.utc) - timedelta(days=2)).timestamp()),
        "period2": int(datetime.now(timezone.utc).timestamp()),
        "interval": interval,
        "includePrePost": "true",
    }
    try:
        resp = _session.get(url, params=params, timeout=15,
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        print(f"[Yahoo] HTTP Error for {symbol}: {e.response.status_code}")
        return None
    except Exception as e:
        print(f"[Yahoo] Error fetching {symbol}: {e}")
        return None

    try:
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        quotes = result["indicators"]["quote"][0]
        ohlc = {
            "timestamp": pd.to_datetime(timestamps, unit="s", utc=True),
            "open": quotes.get("open", []),
            "high": quotes.get("high", []),
            "low": quotes.get("low", []),
            "close": quotes.get("close", []),
            "volume": quotes.get("volume", []),
        }
        df = pd.DataFrame(ohlc)
        df.dropna(subset=["open", "high", "low", "close"], inplace=True)
        if df.empty:
            return None
        df.set_index("timestamp", inplace=True)
        return df
    except (KeyError, IndexError, TypeError) as e:
        print(f"[Yahoo] Parse error for {symbol}: {e}")
        return None


# ---- Unified Interface ----

def fetch_ohlcv(pair_name: str, timeframe: str = "5m", limit: int = 100) -> pd.DataFrame | None:
    if pair_name not in AVAILABLE_PAIRS:
        print(f"[Data] Unknown pair: {pair_name}")
        return None

    pair_info = AVAILABLE_PAIRS[pair_name]
    pair_type = pair_info["type"]

    if pair_type == "crypto":
        symbol = pair_info["binance_symbol"]
        raw = _binance_klines(symbol, timeframe, limit)
        df = binance_to_dataframe(raw)
        if df is not None and len(df) >= 30:
            return df
        return None
    else:
        yahoo_symbol = pair_info["yfinance_symbol"]

        # Handle OTC / exotic pairs with empty yfinance_symbol:
        # strip " OTC" and look up the base pair, or construct XXXYYY=X
        if not yahoo_symbol:
            # Try to derive from the standard pair (e.g. "CAD/JPY OTC" -> "CAD/JPY")
            base_name = pair_name.removesuffix(" OTC").removesuffix(" otc")
            base_info = AVAILABLE_PAIRS.get(base_name)
            if base_info:
                yahoo_symbol = base_info.get("yfinance_symbol", "")
            if not yahoo_symbol:
                # Direct construction: "CAD/JPY" -> "CADJPY=X"
                normalized = pair_name \
                    .removesuffix(" OTC").removesuffix(" otc") \
                    .replace("/", "").upper()
                yahoo_symbol = f"{normalized}=X"

        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m",
            "30m": "30m", "1h": "60m", "4h": "60m",
        }
        yahoo_interval = interval_map.get(timeframe, "5m")
        return _fetch_yahoo_csv(yahoo_symbol, interval=yahoo_interval)


def get_current_price(pair_name: str) -> float | None:
    df = fetch_ohlcv(pair_name, timeframe="1m", limit=2)
    if df is not None and not df.empty:
        return float(df["close"].iloc[-1])
    return None


def get_multiple_timeframes(pair_name: str) -> dict:
    result = {}
    for tf in ["1m", "5m", "15m", "30m", "1h"]:
        df = fetch_ohlcv(pair_name, timeframe=tf, limit=100)
        if df is not None and len(df) >= 30:
            result[tf] = df
    return result
