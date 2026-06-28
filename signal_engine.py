"""
Signal Engine - generates trading signals from technical analysis
Combines multiple indicators for high-confidence signals
"""
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from indicators import (
    rsi, macd, bollinger_bands, stochastic, ema, sma,
    atr, support_resistance, analyze_candle_stick
)
from market_data import get_multiple_timeframes, get_current_price, fetch_ohlcv
from config import AVAILABLE_PAIRS, HIGH_CONFIDENCE, MEDIUM_CONFIDENCE


def _rsi_analysis(df: pd.DataFrame) -> dict:
    """Analyze RSI and return signal + strength"""
    rsi_val = rsi(df["close"], 14)
    if rsi_val.empty or len(rsi_val) < 2:
        return {"signal": "neutral", "strength": 0, "value": 50, "detail": ""}

    current = rsi_val.iloc[-1]
    prev = rsi_val.iloc[-2]

    detail = f"RSI(14): {current:.1f}"
    signal = "neutral"
    strength = 0

    if current < 30:
        signal = "call"  # Oversold → price likely to go UP
        strength = min(90, int((30 - current) * 3 + 60))
        detail += " 📗 Oversold"
    elif current > 70:
        signal = "put"  # Overbought → price likely to go DOWN
        strength = min(90, int((current - 70) * 3 + 60))
        detail += " 📕 Overbought"
    elif current < 40:
        # Bullish zone
        signal = "call" if current > prev else "neutral"
        strength = 40
        detail += " 📗 Bullish zone"
    elif current > 60:
        # Bearish zone
        signal = "put" if current < prev else "neutral"
        strength = 40
        detail += " 📕 Bearish zone"
    else:
        detail += " ⚖️ Neutral"
        strength = 30

    # Divergence check (simplified)
    if len(rsi_val) > 10:
        price_5 = df["close"].iloc[-5]
        rsi_5 = rsi_val.iloc[-5]
        if not pd.isna(price_5) and not pd.isna(rsi_5):
            # Bullish divergence: price lower low, RSI higher low
            if current > rsi_5 and df["close"].iloc[-1] < price_5:
                signal = "call"
                strength = min(95, strength + 25)
                detail += " | Bullish Divergence 🔄"
            # Bearish divergence: price higher high, RSI lower high
            elif current < rsi_5 and df["close"].iloc[-1] > price_5:
                signal = "put"
                strength = min(95, strength + 25)
                detail += " | Bearish Divergence 🔄"

    return {"signal": signal, "strength": strength, "value": float(current), "detail": detail}


def _macd_analysis(df: pd.DataFrame) -> dict:
    """Analyze MACD and return signal + strength"""
    macd_data = macd(df["close"])
    if not macd_data or macd_data["macd"].empty or len(macd_data["macd"]) < 2:
        return {"signal": "neutral", "strength": 0, "detail": ""}

    curr_macd = macd_data["macd"].iloc[-1]
    curr_signal = macd_data["signal"].iloc[-1]
    prev_macd = macd_data["macd"].iloc[-2]
    prev_signal = macd_data["signal"].iloc[-2]
    histogram = macd_data["histogram"].iloc[-1]
    prev_hist = macd_data["histogram"].iloc[-2]

    detail = f"MACD: {curr_macd:.2f} | Signal: {curr_signal:.2f} | Hist: {histogram:.2f}"
    signal = "neutral"
    strength = 0

    # MACD crossover
    if prev_macd < prev_signal and curr_macd > curr_signal:
        signal = "call"  # Bullish crossover
        strength = 75
        detail += " 🟢 Bullish Crossover"
    elif prev_macd > prev_signal and curr_macd < curr_signal:
        signal = "put"  # Bearish crossover
        strength = 75
        detail += " 🔴 Bearish Crossover"

    # Histogram momentum
    elif histogram > 0 and prev_hist <= histogram:
        signal = "call"
        strength = 55
        detail += " 📈 Bullish momentum"
    elif histogram < 0 and prev_hist >= histogram:
        signal = "put"
        strength = 55
        detail += " 📉 Bearish momentum"

    # Position relative to zero line
    elif curr_macd > 0:
        signal = "call"
        strength = 40
        detail += " ⬆ Above zero"
    elif curr_macd < 0:
        signal = "put"
        strength = 40
        detail += " ⬇ Below zero"

    return {"signal": signal, "strength": strength, "detail": detail}


def _bb_analysis(df: pd.DataFrame) -> dict:
    """Analyze Bollinger Bands and return signal + strength"""
    bb = bollinger_bands(df["close"])
    if bb["upper"].empty or len(bb["upper"]) < 2:
        return {"signal": "neutral", "strength": 0, "detail": ""}

    price = df["close"].iloc[-1]
    upper = bb["upper"].iloc[-1]
    lower = bb["lower"].iloc[-1]
    middle = bb["middle"].iloc[-1]
    bandwidth = ((upper - lower) / middle) * 100

    detail = f"BB Upper: {upper:.2f} | Middle: {middle:.2f} | Lower: {lower:.2f}"
    signal = "neutral"
    strength = 0

    # Price touching upper band
    if price >= upper * 0.995:
        signal = "put"
        strength = 70
        detail += " 🔴 Touching upper band"
    # Price touching lower band
    elif price <= lower * 1.005:
        signal = "call"
        strength = 70
        detail += " 🟢 Touching lower band"
    # Squeeze (low bandwidth) - potential breakout
    elif bandwidth < 5:
        signal = "neutral"
        strength = 20
        detail += " ⏸️ Squeeze (breakout soon)"
    # Price near middle
    elif abs(price - middle) / middle < 0.003:
        detail += " ⚖️ At middle band"
        strength = 25
    elif price > middle:
        signal = "call" if price < middle * 1.01 else "neutral"
        strength = 35
        detail += " ⬆ Above middle"
    else:
        signal = "put" if price > middle * 0.99 else "neutral"
        strength = 35
        detail += " ⬇ Below middle"

    return {"signal": signal, "strength": strength, "detail": detail}


def _ema_analysis(df: pd.DataFrame) -> dict:
    """Analyze EMA crossovers and trend"""
    ema9 = ema(df["close"], 9)
    ema21 = ema(df["close"], 21)
    ema50 = ema(df["close"], 50)

    if ema9.empty or ema21.empty:
        return {"signal": "neutral", "strength": 0, "detail": ""}

    price = df["close"].iloc[-1]
    detail = f"EMA9: {ema9.iloc[-1]:.2f} | EMA21: {ema21.iloc[-1]:.2f}"
    signal = "neutral"
    strength = 0

    # Crossover detection
    if ema9.iloc[-2] <= ema21.iloc[-2] and ema9.iloc[-1] > ema21.iloc[-1]:
        signal = "call"
        strength = 80
        detail += " 🟢 Golden Cross (9/21)"
    elif ema9.iloc[-2] >= ema21.iloc[-2] and ema9.iloc[-1] < ema21.iloc[-1]:
        signal = "put"
        strength = 80
        detail += " 🔴 Death Cross (9/21)"

    # Trend direction
    elif ema9.iloc[-1] > ema21.iloc[-1] and not ema50.empty and ema9.iloc[-1] > ema50.iloc[-1]:
        signal = "call"
        strength = 55
        detail += " 📈 Uptrend"
    elif ema9.iloc[-1] < ema21.iloc[-1] and not ema50.empty and ema9.iloc[-1] < ema50.iloc[-1]:
        signal = "put"
        strength = 55
        detail += " 📉 Downtrend"
    elif ema9.iloc[-1] > ema21.iloc[-1]:
        signal = "call"
        strength = 35
        detail += " ↗️ Mild bullish"
    else:
        signal = "put"
        strength = 35
        detail += " ↘️ Mild bearish"

    # Price vs EMA
    if price > ema9.iloc[-1] * 1.02:
        detail += " | Price >> EMA9"
    elif price < ema9.iloc[-1] * 0.98:
        detail += " | Price << EMA9"

    return {"signal": signal, "strength": strength, "detail": detail}


def _stoch_analysis(df: pd.DataFrame) -> dict:
    """Analyze Stochastic oscillator"""
    stoch = stochastic(df["high"], df["low"], df["close"])
    if stoch["k"].empty or len(stoch["k"]) < 2:
        return {"signal": "neutral", "strength": 0, "detail": ""}

    k = stoch["k"].iloc[-1]
    d = stoch["d"].iloc[-1]
    prev_k = stoch["k"].iloc[-2]

    detail = f"Stoch %K: {k:.1f} | %D: {d:.1f}"
    signal = "neutral"
    strength = 0

    if k < 20:
        signal = "call"
        strength = 65
        detail += " 🟢 Oversold"
    elif k > 80:
        signal = "put"
        strength = 65
        detail += " 🔴 Overbought"
    elif prev_k < d and k > d:
        signal = "call"
        strength = 45
        detail += " 🟢 Bullish cross"
    elif prev_k > d and k < d:
        signal = "put"
        strength = 45
        detail += " 🔴 Bearish cross"
    else:
        strength = 20
        detail += " ⚖️ Neutral"

    return {"signal": signal, "strength": strength, "detail": detail}


def _volume_analysis(df: pd.DataFrame) -> dict:
    """Analyze volume for confirmation"""
    vol = df["volume"]
    if vol.empty or len(vol) < 5:
        return {"signal": "neutral", "strength": 0, "detail": ""}

    avg_vol = vol.tail(5).mean()
    curr_vol = vol.iloc[-1]

    if avg_vol == 0:
        return {"signal": "neutral", "strength": 0, "detail": "Volume: N/A"}

    vol_ratio = curr_vol / avg_vol
    detail = f"Vol: {curr_vol:.0f} | Avg(5): {avg_vol:.0f} | Ratio: {vol_ratio:.2f}x"

    if vol_ratio > 2.0:
        signal = "confirm"  # High volume confirms the move
        strength = 80
        detail += " 🟢 High volume"
    elif vol_ratio > 1.5:
        signal = "confirm"
        strength = 60
        detail += " 📊 Above avg"
    elif vol_ratio < 0.5:
        signal = "weak"
        strength = 30
        detail += " 🔇 Low volume"
    else:
        signal = "neutral"
        strength = 40
        detail += " 📊 Normal"

    return {"signal": signal, "strength": strength, "detail": detail}


def _calculate_risk_score(df: pd.DataFrame, signal: dict) -> dict:
    """Calculate risk score (1-10) for a signal based on multiple factors.
    
    Lower score = lower risk, Higher score = higher risk.
    Factors: volatility, volume, confidence inverse, pattern clarity.
    """
    risk = 5  # Start at medium
    factors = []

    # 1. Volatility factor (ATR as % of price)
    atr_val = atr(df["high"], df["low"], df["close"])
    if not atr_val.empty and len(atr_val) > 0:
        current_price = df["close"].iloc[-1]
        atr_pct = (atr_val.iloc[-1] / current_price) * 100 if current_price > 0 else 0
        if atr_pct > 5:
            risk += 3
            factors.append(f"⚡ High volatility ({atr_pct:.1f}%)")
        elif atr_pct > 2:
            risk += 1.5
            factors.append(f"📊 Moderate volatility ({atr_pct:.1f}%)")
        else:
            risk -= 1
            factors.append(f"💤 Low volatility ({atr_pct:.1f}%)")
    else:
        factors.append("📊 Volatility: N/A")

    # 2. Volume factor
    vol = df["volume"]
    if not vol.empty and len(vol) > 5:
        avg_vol = vol.tail(5).mean()
        curr_vol = vol.iloc[-1]
        if avg_vol > 0:
            vol_ratio = curr_vol / avg_vol
            if vol_ratio < 0.5:
                risk += 2
                factors.append("🔇 Low volume (illiquid)")
            elif vol_ratio < 0.8:
                risk += 0.5
                factors.append("📉 Below avg volume")
            elif vol_ratio > 2.0:
                risk -= 1.5
                factors.append("🟢 High volume (confirmation)")
            elif vol_ratio > 1.5:
                risk -= 0.5
                factors.append("📊 Above avg volume")
            else:
                factors.append("📊 Normal volume")
    else:
        factors.append("📊 Volume: N/A")

    # 3. Confidence factor (higher confidence = lower risk)
    confidence = signal.get("confidence", 50)
    if confidence >= 75:
        risk -= 2
        factors.append("🟢 High confidence signal")
    elif confidence >= 55:
        risk -= 0.5
        factors.append("🟡 Moderate confidence")
    elif confidence >= 40:
        risk += 0.5
        factors.append("🟠 Low confidence")
    else:
        risk += 2
        factors.append("🔴 Very low confidence")

    # 4. Trend clarity
    ema9 = ema(df["close"], 9)
    ema21 = ema(df["close"], 21)
    if not ema9.empty and not ema21.empty:
        ema9_v = ema9.iloc[-1]
        ema21_v = ema21.iloc[-1]
        ema_diff_pct = abs(ema9_v - ema21_v) / max(ema21_v, 0.001) * 100
        if ema_diff_pct > 1.0:
            risk -= 1.5
            factors.append(f"📈 Strong trend ({ema_diff_pct:.2f}%)")
        elif ema_diff_pct > 0.3:
            risk -= 0.5
            factors.append(f"📊 Moderate trend")
        else:
            risk += 1
            factors.append("⚖️ Weak / choppy trend")
    else:
        factors.append("⚖️ Trend: N/A")

    # 5. Pattern clarity
    candle = signal.get("candle_pattern", "")
    if candle and any(p in candle for p in ["☀️", "🌙", "⚔️", "🐦‍⬛", "🔥", "💧"]):
        risk -= 1
        factors.append(f"🕯️ Strong pattern ({candle.split(' ')[-1]})")
    elif candle and any(p in candle for p in ["📈", "📉", "🟢", "🔴"]):
        risk -= 0.5
        factors.append(f"🕯️ Clear pattern ({candle.split(' ')[-1]})")
    elif not candle:
        risk += 0.5
        factors.append("🕯️ No clear pattern")
    else:
        factors.append(f"🕯️ {candle.split(' ')[-1] if ' ' in candle else candle}")

    # Clamp risk to 1-10
    risk = max(1, min(10, int(round(risk))))
    
    # Label
    if risk <= 4:
        label = "LOW 🟢"
    elif risk <= 7:
        label = "MEDIUM 🟡"
    else:
        label = "HIGH 🔴"

    return {
        "score": risk,
        "label": label,
        "factors": factors,
    }


def generate_signal(pair_name: str, timeframe: str = "5m") -> dict | None:
    """
    Generate a complete trading signal for a pair.
    Combines RSI, MACD, Bollinger Bands, EMA, and Stochastic.

    Returns:
        dict with signal details or None if data unavailable
    """
    df = fetch_ohlcv(pair_name, timeframe, limit=100)
    if df is None or len(df) < 30:
        print(f"[Signal] Insufficient data for {pair_name} on {timeframe}")
        return None

    # Run all analyses
    rsi_result = _rsi_analysis(df)
    macd_result = _macd_analysis(df)
    bb_result = _bb_analysis(df)
    ema_result = _ema_analysis(df)
    stoch_result = _stoch_analysis(df)
    vol_result = _volume_analysis(df)

    # Candlestick pattern
    candle_pattern = analyze_candle_stick(df["open"], df["high"], df["low"], df["close"])

    # Support & Resistance
    sr = support_resistance(df["close"], 20)
    atr_val = atr(df["high"], df["low"], df["close"])
    current_atr = float(atr_val.iloc[-1]) if not atr_val.empty else 0

    # Consensus scoring
    analyses = [
        ("RSI", rsi_result),
        ("MACD", macd_result),
        ("Bollinger", bb_result),
        ("EMA", ema_result),
        ("Stochastic", stoch_result),
    ]

    call_score = 0
    put_score = 0
    total_weight = 0
    details = []

    weights = {"RSI": 1.2, "MACD": 1.3, "Bollinger": 1.0, "EMA": 1.3, "Stochastic": 0.8}

    for name, result in analyses:
        sig = result.get("signal", "neutral")
        strength = result.get("strength", 0)
        detail = result.get("detail", "")
        weight = weights.get(name, 1.0)

        if sig == "call":
            call_score += strength * weight
            total_weight += weight
        elif sig == "put":
            put_score += strength * weight
            total_weight += weight

        details.append(f"  {name}: {detail}")

    # Volume confirmation
    if vol_result["signal"] == "confirm":
        if call_score > put_score:
            call_score *= 1.1
        else:
            put_score *= 1.1

    # Calculate final direction and confidence
    if total_weight == 0:
        direction = "NEUTRAL"
        confidence = 30
    elif call_score > put_score:
        confidence = min(90, int(call_score / total_weight))
        direction = "CALL"
    elif put_score > call_score:
        confidence = min(90, int(put_score / total_weight))
        direction = "PUT"
    else:
        direction = "NEUTRAL"
        confidence = 30

    # Price info
    current_price = df["close"].iloc[-1]
    price_change = df["close"].iloc[-1] - df["close"].iloc[-5]
    price_change_pct = (price_change / df["close"].iloc[-5]) * 100

    # Trend info
    ema9 = ema(df["close"], 9).iloc[-1]
    ema21 = ema(df["close"], 21).iloc[-1]
    trend = "uptrend 📈" if ema9 > ema21 else "downtrend 📉"

    # Recalculate risk with actual confidence
    risk_data = _calculate_risk_score(df, {
        "confidence": confidence,
        "candle_pattern": candle_pattern,
        "trend": trend,
    })

    # Volatility
    bb_data = bollinger_bands(df["close"])
    bb_width = ((bb_data["upper"].iloc[-1] - bb_data["lower"].iloc[-1]) / bb_data["middle"].iloc[-1]) * 100
    volatility = "high" if bb_width > 8 else "medium" if bb_width > 4 else "low"

    return {
        "pair": pair_name,
        "timeframe": timeframe,
        "direction": direction,
        "confidence": confidence,
        "current_price": current_price,
        "price_change": price_change,
        "price_change_pct": price_change_pct,
        "trend": trend,
        "volatility": volatility,
        "atr": current_atr,
        "support": sr["support"],
        "resistance": sr["resistance"],
        "candle_pattern": candle_pattern,
        "risk_score": risk_data,  # {score: int, label: str, factors: [...]}
        "details": details,
        "timestamp": datetime.now(timezone.utc),
        "analyses": {
            "rsi": rsi_result,
            "macd": macd_result,
            "bb": bb_result,
            "ema": ema_result,
            "stoch": stoch_result,
            "volume": vol_result,
        }
    }


def generate_full_analysis(pair_name: str) -> dict | None:
    """
    Generate a comprehensive multi-timeframe market analysis.
    """
    timeframes = get_multiple_timeframes(pair_name)
    if not timeframes:
        return None

    signals = {}
    for tf, df in timeframes.items():
        sig = generate_signal(pair_name, tf)
        if sig:
            signals[tf] = sig

    pair_info = AVAILABLE_PAIRS.get(pair_name, {})
    current_price = get_current_price(pair_name)

    return {
        "pair": pair_name,
        "type": pair_info.get("type", "unknown"),
        "current_price": current_price,
        "signals": signals,
        "timestamp": datetime.now(timezone.utc),
    }
