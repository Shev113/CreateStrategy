import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from core.moex_session import MOEX_SESSION


SECTOR_INDEX_MAP = {
    'Нефть и газ': 'MOEXOG',
    'Электроэнергетика': 'MOEXEU',
    'Металлы и добыча': 'MOEXMM',
    'Финансы': 'MOEXFN',
    'Потребительский сектор': 'MOEXCN',
    'Строительство': 'MOEXRE',
    'Телекоммуникации': 'MOEXTL',
    'IT': 'MOEXIT',
    'Химия': 'MOEXCH',
    'Транспорт': 'MOEXTN',
}


def _fetch_index_candles(index_ticker, days=30):
    base_url = f"https://iss.moex.com/iss/engines/stock/markets/index/boards/SNDX/securities/{index_ticker}/candles.json"
    params = {"interval": 24}
    try:
        response = MOEX_SESSION.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "candles" in data and "data" in data["candles"]:
            candles = data["candles"]["data"]
            if candles:
                return [float(c[1]) for c in candles if c and len(c) >= 2]
    except Exception as e:
        logging.debug(f'Failed to fetch {index_ticker}: {e}')
    return None


def calc_sector_rotation(sector_tickers_map=None, period=20):
    results = []
    index_map = dict(SECTOR_INDEX_MAP)

    if sector_tickers_map:
        for sector in sector_tickers_map:
            if sector not in index_map:
                index_map[sector] = None

    fetch_items = [(sector, idx) for sector, idx in index_map.items() if idx]
    closes_map = {}

    with ThreadPoolExecutor(max_workers=5) as pool:
        fut_to_sector = {
            pool.submit(_fetch_index_candles, idx, period + 10): sector
            for sector, idx in fetch_items
        }
        for f in as_completed(fut_to_sector, timeout=60):
            sector = fut_to_sector[f]
            try:
                closes = f.result()
                if closes and len(closes) >= 5:
                    closes_map[sector] = closes
            except Exception:
                pass

    for sector, closes in closes_map.items():
        ret_5d = ((closes[-1] / closes[-6]) - 1) * 100 if len(closes) >= 6 else 0
        ret_10d = ((closes[-1] / closes[-11]) - 1) * 100 if len(closes) >= 11 else 0
        ret_20d = ((closes[-1] / closes[-21]) - 1) * 100 if len(closes) >= 21 else 0
        avg_ret = (ret_5d + ret_10d + ret_20d) / 3 if ret_20d != 0 else (ret_5d + ret_10d) / 2

        if ret_5d > 1 and ret_10d > 0:
            trend = 'Усиление'
        elif ret_5d < -1 and ret_10d < 0:
            trend = 'Ослабление'
        else:
            trend = 'Нейтрально'

        ticker_count = 0
        if sector_tickers_map and sector in sector_tickers_map:
            ticker_count = len(sector_tickers_map[sector])

        results.append({
            'sector': sector,
            'ret_5d': round(ret_5d, 1),
            'ret_10d': round(ret_10d, 1),
            'ret_20d': round(ret_20d, 1),
            'avg_ret': round(avg_ret, 1),
            'trend': trend,
            'ticker_count': ticker_count,
        })

    results.sort(key=lambda x: x['avg_ret'], reverse=True)
    return results


def calc_sector_rotation_async(on_complete, sector_tickers_map=None, period=20):
    def task():
        try:
            result = calc_sector_rotation(sector_tickers_map, period)
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
            logging.warning(f'Sector rotation error: {e}')
            if on_complete:
                try:
                    import tkinter as tk
                    root = tk._default_root
                    if root is not None:
                        root.after(0, on_complete, [])
                    else:
                        on_complete([])
                except Exception:
                    on_complete([])

    threading.Thread(target=task, daemon=True).start()
