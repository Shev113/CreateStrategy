# breadth.py
import logging
import numpy as np
import pandas as pd


class BreadthIndicator:
    def __init__(self, ma_period=50):
        self.ma_period = ma_period

    def calculate(self, ticker_closes, period=None):
        if not ticker_closes:
            return None

        ma_period = period or self.ma_period
        above_count = 0
        total_count = 0

        above_items = []
        below_items = []

        for ticker, closes in ticker_closes.items():
            if closes is None or len(closes) < ma_period + 1:
                continue

            try:
                series = pd.Series(closes)
                ma = series.rolling(ma_period).mean()
                last_close = float(series.iloc[-1])
                last_ma = float(ma.iloc[-1])

                if not np.isnan(last_ma):
                    total_count += 1
                    item = {'ticker': ticker, 'close': round(last_close, 2), 'ma': round(last_ma, 2)}
                    if last_close > last_ma:
                        above_count += 1
                        above_items.append(item)
                    else:
                        below_items.append(item)
            except Exception:
                continue

        if total_count == 0:
            return None

        pct = above_count / total_count * 100
        zone = 'neutral'
        if pct >= 70:
            zone = 'overbought'
        elif pct <= 30:
            zone = 'oversold'

        above_items.sort(key=lambda x: ((x['close'] - x['ma']) / x['ma'] * 100), reverse=True)
        below_items.sort(key=lambda x: ((x['ma'] - x['close']) / x['ma'] * 100), reverse=True)

        return {
            'above_pct': round(pct, 1),
            'above_count': above_count,
            'total_count': total_count,
            'zone': zone,
            'above_items': above_items,
            'below_items': below_items,
        }
