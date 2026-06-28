"""
Technical Indicators - pure numpy/pandas implementation
No external TA library needed.
"""
import numpy as np
import pandas as pd


def sma(data: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average"""
    return data.rolling(window=period).mean()


def ema(data: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average"""
    return data.ewm(span=period, adjust=False).mean()


def rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index
    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain / Average Loss
    """
    delta = data.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Wilder's smoothing
    for i in range(period, len(avg_gain)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """
    MACD (Moving Average Convergence Divergence)
    Returns: {'macd': pd.Series, 'signal': pd.Series, 'histogram': pd.Series}
    """
    ema_fast = ema(data, fast)
    ema_slow = ema(data, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }


def bollinger_bands(data: pd.Series, period: int = 20, std_dev: float = 2.0) -> dict:
    """
    Bollinger Bands
    Returns: {'upper': pd.Series, 'middle': pd.Series, 'lower': pd.Series}
    """
    middle = sma(data, period)
    std = data.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return {"upper": upper, "middle": middle, "lower": lower}


def stochastic(data_high: pd.Series, data_low: pd.Series, data_close: pd.Series,
               k_period: int = 14, d_period: int = 3) -> dict:
    """Stochastic Oscillator %K and %D"""
    low_min = data_low.rolling(window=k_period).min()
    high_max = data_high.rolling(window=k_period).max()
    k = 100 * ((data_close - low_min) / (high_max - low_min))
    d = sma(k, d_period)
    return {"k": k, "d": d}


def atr(data_high: pd.Series, data_low: pd.Series, data_close: pd.Series,
        period: int = 14) -> pd.Series:
    """Average True Range"""
    high_low = data_high - data_low
    high_close = np.abs(data_high - data_close.shift())
    low_close = np.abs(data_low - data_close.shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr_val = tr.rolling(window=period).mean()
    return atr_val


def ichimoku(data_high: pd.Series, data_low: pd.Series,
             tenkan: int = 9, kijun: int = 26, senkou_b: int = 52) -> dict:
    """Ichimoku Cloud indicators"""
    tenkan_sen = (data_high.rolling(tenkan).max() + data_low.rolling(tenkan).min()) / 2
    kijun_sen = (data_high.rolling(kijun).max() + data_low.rolling(kijun).min()) / 2
    senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun)
    senkou_span_b = ((data_high.rolling(senkou_b).max() +
                      data_low.rolling(senkou_b).min()) / 2).shift(kijun)
    chikou_span = data_high.shift(-kijun)  # actually close price shifted back
    return {
        "tenkan_sen": tenkan_sen,
        "kijun_sen": kijun_sen,
        "senkou_span_a": senkou_span_a,
        "senkou_span_b": senkou_span_b,
        "chikou_span": chikou_span,
    }


def support_resistance(data: pd.Series, lookback: int = 20) -> dict:
    """
    Find support and resistance levels using swing highs/lows
    Returns: {'support': float, 'resistance': float}
    """
    recent = data.tail(lookback)
    resistance = recent.max()
    support = recent.min()
    return {"support": support, "resistance": resistance}


def analyze_candle_stick(open_p: pd.Series, high_p: pd.Series,
                         low_p: pd.Series, close_p: pd.Series) -> str:
    """
    Comprehensive candlestick pattern detection
    Returns pattern name or empty string
    """
    # Need at least 5 candles for multi-candle patterns
    if len(close_p) < 5:
        return ""

    def get_candle(i):
        """Helper to get candle properties at index i"""
        o, h, l, c = open_p.iloc[i], high_p.iloc[i], low_p.iloc[i], close_p.iloc[i]
        body = abs(c - o)
        total = h - l
        upper = h - max(c, o)
        lower = min(c, o) - l
        is_green = c > o
        is_red = c < o
        mid = (h + l) / 2
        return {"o": o, "h": h, "l": l, "c": c, "body": body, "range": total,
                "upper": upper, "lower": lower, "is_green": is_green, "is_red": is_red, "mid": mid}

    c5 = get_candle(-5)
    c4 = get_candle(-4)
    c3 = get_candle(-3)
    c2 = get_candle(-2)
    c1 = get_candle(-1)

    # ==================== 3-CANDLE PATTERNS ====================

    # Morning Star (Bullish Reversal) ☀️
    # Long bearish → small body (star) → long bullish
    if (c3["is_red"] and c3["body"] > c3["range"] * 0.6 and
        c2["body"] < c2["range"] * 0.3 and
        c1["is_green"] and c1["body"] > c1["range"] * 0.6 and
        c1["c"] > (c3["o"] + c3["c"]) / 2):
        return "Morning Star ☀️"

    # Evening Star (Bearish Reversal) 🌙
    # Long bullish → small body (star) → long bearish
    if (c3["is_green"] and c3["body"] > c3["range"] * 0.6 and
        c2["body"] < c2["range"] * 0.3 and
        c1["is_red"] and c1["body"] > c1["range"] * 0.6 and
        c1["c"] < (c3["o"] + c3["c"]) / 2):
        return "Evening Star 🌙"

    # Three White Soldiers (Bullish) ⚔️
    if (c3["is_green"] and c2["is_green"] and c1["is_green"] and
        c3["body"] > c3["range"] * 0.4 and c2["body"] > c2["range"] * 0.4 and c1["body"] > c1["range"] * 0.4 and
        c3["c"] >= c2["o"] and c2["c"] >= c1["o"] and
        c3["c"] < c2["c"] < c1["c"]):
        return "Three White Soldiers ⚔️"

    # Three Black Crows (Bearish) 🐦‍⬛
    if (c3["is_red"] and c2["is_red"] and c1["is_red"] and
        c3["body"] > c3["range"] * 0.4 and c2["body"] > c2["range"] * 0.4 and c1["body"] > c1["range"] * 0.4 and
        c3["c"] <= c2["o"] and c2["c"] <= c1["o"] and
        c3["c"] > c2["c"] > c1["c"]):
        return "Three Black Crows 🐦‍⬛"

    # ==================== 2-CANDLE PATTERNS ====================

    # Bullish Engulfing 🔥
    if (c1["is_green"] and c2["is_red"] and
        c1["o"] < c2["c"] and c1["c"] > c2["o"]):
        return "Bullish Engulfing 🔥"

    # Bearish Engulfing 💧
    if (c1["is_red"] and c2["is_green"] and
        c1["o"] > c2["c"] and c1["c"] < c2["o"]):
        return "Bearish Engulfing 💧"

    # Bullish Harami 🔺
    if (c2["is_red"] and c1["is_green"] and
        c1["body"] < c2["body"] * 0.6 and
        c1["o"] > c2["c"] and c1["c"] < c2["o"]):
        return "Bullish Harami 🔺"

    # Bearish Harami 🔻
    if (c2["is_green"] and c1["is_red"] and
        c1["body"] < c2["body"] * 0.6 and
        c1["o"] < c2["c"] and c1["c"] > c2["o"]):
        return "Bearish Harami 🔻"

    # Piercing Line ⚔️ (Bullish)
    if (c2["is_red"] and c1["is_green"] and
        c1["o"] <= c2["l"] and c1["c"] > (c2["o"] + c2["c"]) / 2 and c1["c"] < c2["o"]):
        return "Piercing Line ⚔️"

    # Dark Cloud Cover ☁️ (Bearish)
    if (c2["is_green"] and c1["is_red"] and
        c1["o"] >= c2["h"] and c1["c"] < (c2["o"] + c2["c"]) / 2 and c1["c"] > c2["o"]):
        return "Dark Cloud Cover ☁️"

    # Tweezer Top (Bearish) 🔝
    if (c2["is_green"] and c1["is_red"] and
        abs(c2["h"] - c1["h"]) / max(c2["h"], 0.001) < 0.001 and
        c1["body"] > c1["range"] * 0.3):
        return "Tweezer Top 🔝"

    # Tweezer Bottom (Bullish) 🔝
    if (c2["is_red"] and c1["is_green"] and
        abs(c2["l"] - c1["l"]) / max(c2["l"], 0.001) < 0.001 and
        c1["body"] > c1["range"] * 0.3):
        return "Tweezer Bottom 🔝"

    # ==================== SINGLE-CANDLE PATTERNS ====================

    # Doji family (tiny body)
    rng = max(c1["range"], 0.0001)
    if c1["body"] / rng < 0.1:
        if c1["upper"] > 2 * c1["lower"] and c1["upper"] > c1["body"]:
            return "Gravestone Doji 🔻"
        elif c1["lower"] > 2 * c1["upper"] and c1["lower"] > c1["body"]:
            return "Dragonfly Doji 🔺"
        return "Doji ⚖️"

    # Hammer / Inverted Hammer (Bullish)
    if c1["lower"] > 2 * c1["body"] and c1["lower"] > 2 * c1["upper"]:
        return "Hammer 🔨"
    if c1["upper"] > 2 * c1["body"] and c1["upper"] > 2 * c1["lower"] and c1["is_green"]:
        return "Inverted Hammer 🔨"

    # Hanging Man (Bearish)
    if c1["lower"] > 2 * c1["body"] and c1["lower"] > 2 * c1["upper"] and c1["is_red"]:
        return "Hanging Man 🚹"

    # Shooting Star (Bearish)
    if c1["upper"] > 2 * c1["body"] and c1["upper"] > 2 * c1["lower"] and c1["is_red"]:
        return "Shooting Star ⭐"

    # Spinning Top (Indecision)
    if c1["body"] < c1["range"] * 0.3:
        return "Spinning Top ⚖️"

    # Marubozu (Strong trend)
    if c1["body"] > c1["range"] * 0.8:
        if c1["upper"] < c1["body"] * 0.1 and c1["lower"] < c1["body"] * 0.1:
            if c1["is_green"]:
                return "Bullish Marubozu 📈"
            return "Bearish Marubozu 📉"

    # Long body candle (strong move)
    if c1["body"] > c1["range"] * 0.7:
        if c1["is_green"]:
            return "Strong Bullish Candle 🟢"
        return "Strong Bearish Candle 🔴"

    return ""
