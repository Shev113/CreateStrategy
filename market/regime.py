# regime.py
import json
import logging
import os
import threading
import time

import numpy as np
import pandas as pd
import requests
import urllib3

from utils import app_dir

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REGIME_TRENDING_UP = 'TRENDING_UP'
REGIME_TRENDING_DOWN = 'TRENDING_DOWN'
REGIME_RANGING = 'RANGING'
REGIME_CRISIS = 'CRISIS'

REGIME_LABELS = {
    REGIME_TRENDING_UP: 'Тренд ↑',
    REGIME_TRENDING_DOWN: 'Тренд ↓',
    REGIME_RANGING: 'Флэт',
    REGIME_CRISIS: 'Кризис',
}

REGIME_STRATEGY_RECOMMENDATIONS = {
    REGIME_TRENDING_UP: [
        'breakout', 'trend', 'system_d', 'dual_thrust', 'dyn_breakout',
        'donchian', 'channel_breakout',
    ],
    REGIME_TRENDING_DOWN: [
        'rsi_levels', 'fisher', 'smi', 'psychological', 'inverse_fisher',
    ],
    REGIME_RANGING: [
        'bounce', 'rsi_levels', 'cog', 'eco', 'dinapoli',
        'keltner', 'vwap_revert',
    ],
    REGIME_CRISIS: [],
}

IMOEX_CACHE_PATH = os.path.join(app_dir(), 'results', 'imoex_cache.json')
IMOEX_CACHE_TTL = 86400


def fetch_imoex_candles(start_date=None, end_date=None, interval=24):
    base_url = "https://iss.moex.com/iss/engines/stock/markets/index/boards/SNDX/securities/IMOEX/candles.json"
    params = {"interval": interval}
    if start_date:
        params["from"] = start_date
    if end_date:
        params["till"] = end_date

    try:
        response = requests.get(base_url, params=params, timeout=30, verify=False)
        response.raise_for_status()
        data = response.json()
        if "candles" in data and "data" in data["candles"]:
            return data["candles"]["data"]
    except Exception as e:
        logging.warning(f"Failed to fetch IMOEX candles: {e}")
    return []


def load_imoex_candles(start_date=None, end_date=None):
    cache_valid = False
    candles = None

    if os.path.exists(IMOEX_CACHE_PATH):
        try:
            mtime = os.path.getmtime(IMOEX_CACHE_PATH)
            if time.time() - mtime < IMOEX_CACHE_TTL:
                with open(IMOEX_CACHE_PATH, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                candles = cache.get('candles')
                if candles and len(candles) > 50:
                    cache_valid = True
        except Exception:
            pass

    if not cache_valid:
        from datetime import datetime, timedelta
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        candles = fetch_imoex_candles(start_date, end_date)
        if candles:
            try:
                os.makedirs(os.path.dirname(IMOEX_CACHE_PATH), exist_ok=True)
                with open(IMOEX_CACHE_PATH, 'w', encoding='utf-8') as f:
                    json.dump({'candles': candles}, f)
            except Exception:
                pass

    return candles or []


def candles_to_df(candles_list):
    valid = [c for c in candles_list if c is not None and len(c) > 6]
    if not valid:
        return None
    return pd.DataFrame(
        valid,
        columns=['Open', 'Close', 'High', 'Low',
                 'Volume', 'Value', 'Begin', 'End'],
        index=pd.to_datetime([c[6] for c in valid], format='mixed')
    )


class MarketRegimeDetector:
    def __init__(self, adx_period=14, adx_trend_threshold=25,
                 adx_flat_threshold=20, ma_period=50,
                 crisis_return_pct=-5.0, crisis_atr_mult=2.0,
                 atr_period=14, atr_long_period=50):
        self.adx_period = adx_period
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_flat_threshold = adx_flat_threshold
        self.ma_period = ma_period
        self.crisis_return_pct = crisis_return_pct
        self.crisis_atr_mult = crisis_atr_mult
        self.atr_period = atr_period
        self.atr_long_period = atr_long_period

    def detect(self, candles_list):
        if not candles_list or len(candles_list) < self.ma_period + self.adx_period + 5:
            return _unknown_regime()

        df = candles_to_df(candles_list)
        if df is None or len(df) < self.ma_period + self.adx_period + 5:
            return _unknown_regime()

        from strategy.indicators import calc_adx, calc_atr

        adx, plus_di, minus_di = calc_adx(df, self.adx_period)
        atr_series = calc_atr(df, self.atr_period)
        atr_long = calc_atr(df, self.atr_long_period)

        last_idx = len(df) - 1
        last_adx = float(adx.iloc[last_idx]) if not pd.isna(adx.iloc[last_idx]) else 0
        last_plus_di = float(plus_di.iloc[last_idx]) if not pd.isna(plus_di.iloc[last_idx]) else 0
        last_minus_di = float(minus_di.iloc[last_idx]) if not pd.isna(minus_di.iloc[last_idx]) else 0

        last_close = float(df['Close'].iloc[last_idx])
        ma = float(df['Close'].iloc[max(0, last_idx - self.ma_period + 1):last_idx + 1].mean())

        recent_closes = df['Close'].astype(float).iloc[-20:]
        recent_return = (float(recent_closes.iloc[-1]) / float(recent_closes.iloc[0]) - 1) * 100

        last_atr = float(atr_series.iloc[last_idx]) if not pd.isna(atr_series.iloc[last_idx]) else 0
        last_atr_long = float(atr_long.iloc[last_idx]) if not pd.isna(atr_long.iloc[last_idx]) else 1
        atr_ratio = last_atr / last_atr_long if last_atr_long > 0 else 1

        regime = REGIME_RANGING
        confidence = 0.0
        details = {
            'adx': round(last_adx, 2),
            'plus_di': round(last_plus_di, 2),
            'minus_di': round(last_minus_di, 2),
            'ma': round(ma, 2),
            'close': round(last_close, 2),
            'recent_return': round(recent_return, 2),
            'atr_ratio': round(atr_ratio, 2),
        }

        if recent_return <= self.crisis_return_pct and atr_ratio >= self.crisis_atr_mult:
            regime = REGIME_CRISIS
            confidence = min(abs(recent_return) / abs(self.crisis_return_pct), 1.0)
        elif last_adx >= self.adx_trend_threshold:
            if last_close > ma and last_plus_di > last_minus_di:
                regime = REGIME_TRENDING_UP
                confidence = min(last_adx / 50.0, 1.0)
            elif last_close < ma and last_minus_di > last_plus_di:
                regime = REGIME_TRENDING_DOWN
                confidence = min(last_adx / 50.0, 1.0)
            else:
                regime = REGIME_RANGING
                confidence = 0.3
        elif last_adx <= self.adx_flat_threshold:
            regime = REGIME_RANGING
            confidence = 1.0 - last_adx / self.adx_flat_threshold

        details['confidence'] = round(confidence, 2)

        return {
            'regime': regime,
            'label': REGIME_LABELS.get(regime, regime),
            'confidence': round(confidence, 2),
            'details': details,
            'recommended_strategies': REGIME_STRATEGY_RECOMMENDATIONS.get(regime, []),
        }

    def detect_async(self, on_complete):
        def task():
            try:
                candles = load_imoex_candles()
                result = self.detect(candles)
                if on_complete:
                    try:
                        import tkinter as tk
                        root = tk._default_root
                        if root is not None:
                            root.after(0, on_complete, result)
                        else:
                            on_complete(result)
                    except Exception:
                        on_complete(result)
            except Exception as e:
                logging.exception('Market regime detection error')
                if on_complete:
                    try:
                        import tkinter as tk
                        root = tk._default_root
                        if root is not None:
                            root.after(0, on_complete, _unknown_regime())
                        else:
                            on_complete(_unknown_regime())
                    except Exception:
                        on_complete(_unknown_regime())

        t = threading.Thread(target=task, daemon=True)
        t.start()


def _unknown_regime():
    return {
        'regime': REGIME_RANGING,
        'label': REGIME_LABELS[REGIME_RANGING],
        'confidence': 0.0,
        'details': {},
        'recommended_strategies': [],
    }
