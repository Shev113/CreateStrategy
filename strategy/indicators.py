# indicators.py
import pandas as pd
import numpy as np


def calc_atr(df, period=14):
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    close = df['Close'].astype(float)
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_avg_volume(df, period=14):
    return df['Volume'].astype(float).rolling(period).mean()


def calc_rsi(df, period=14):
    close = df['Close'].astype(float)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def is_bullish_rejection(close, high, low):
    c, h, l = float(close), float(high), float(low)
    if h == l:
        return False
    return c > (h + l) / 2


def is_bearish_rejection(close, high, low):
    c, h, l = float(close), float(high), float(low)
    if h == l:
        return False
    return c < (h + l) / 2


def calc_adx(df, period=14):
    high = df['High'].astype(float)
    low = df['Low'].astype(float)
    close = df['Close'].astype(float)

    prev_high = high.shift(1)
    prev_low = low.shift(1)

    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm_raw = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm_raw = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    atr = calc_atr(df, period)

    plus_dm_smooth = plus_dm_raw.ewm(alpha=1.0 / period, adjust=False).mean()
    minus_dm_smooth = minus_dm_raw.ewm(alpha=1.0 / period, adjust=False).mean()
    atr_smooth = atr.ewm(alpha=1.0 / period, adjust=False).mean()

    atr_safe = atr_smooth.replace(0, np.nan)

    plus_di = 100 * plus_dm_smooth / atr_safe
    minus_di = 100 * minus_dm_smooth / atr_safe

    di_sum = plus_di + minus_di
    di_sum = di_sum.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / di_sum

    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()
    return adx, plus_di, minus_di
