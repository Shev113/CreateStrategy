import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from core.moex_cache import moex_cache, cached_get_tickers

INDEX_TO_SECTOR = {
    'MOEXOG': 'Нефть и газ',
    'MOEXFN': 'Банки и финансы',
    'MOEXMM': 'Металлы и добыча',
    'MOEXCN': 'Потребление и ритейл',
    'MOEXEU': 'Электроэнергетика',
    'MOEXCH': 'Химия и удобрения',
    'MOEXTN': 'Транспорт и машиностроение',
    'MOEXTL': 'IT и телеком',
    'MOEXIT': 'IT и телеком',
    'MOEXRE': 'Строительство и недвижимость',
}

ANALYTICS_URL = (
    'https://iss.moex.com/iss/statistics/engines/'
    'stock/markets/index/analytics/{index_id}.json?iss.meta=off'
)

ALL_TICKERS_URL = (
    'https://iss.moex.com/iss/engines/stock/markets/'
    'shares/boards/TQBR/securities.json?iss.meta=off'
)


def fetch_all_moex_tickers():
    cached = moex_cache.get('moex_tickers_tqbr')
    if cached is not None:
        return cached
    response = requests.get(ALL_TICKERS_URL, timeout=15, verify=False)
    response.raise_for_status()
    data = response.json()
    result = [row[0] for row in data['securities']['data']]
    if result:
        moex_cache.set('moex_tickers_tqbr', result, 4 * 3600)
        moex_cache.flush()
    return result


def fetch_index_tickers(index_id):
    url = ANALYTICS_URL.format(index_id=index_id)
    response = requests.get(url, timeout=15, verify=False)
    response.raise_for_status()
    data = response.json()
    for block_name in ('analytics', 'indices'):
        block = data.get(block_name)
        if block is None or 'columns' not in block:
            continue
        try:
            ticker_col = block['columns'].index('ticker')
        except ValueError:
            try:
                ticker_col = block['columns'].index('SECID')
            except ValueError:
                continue
        return [row[ticker_col].upper()
                for row in block.get('data', [])
                if row and len(row) > ticker_col and row[ticker_col]]
    return []


def fetch_all_sector_tickers():
    return fetch_all_sector_tickers_parallel()


def fetch_all_sector_tickers_parallel(max_workers=10):
    result = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fut_to_idx = {
            pool.submit(fetch_index_tickers, idx): idx
            for idx in INDEX_TO_SECTOR
        }
        for f in as_completed(fut_to_idx, timeout=30):
            idx = fut_to_idx[f]
            try:
                tickers = f.result()
                sector = INDEX_TO_SECTOR[idx]
                for t in tickers:
                    if t not in result:
                        result[t] = sector
            except Exception:
                logging.warning("Failed to fetch MOEX index %s", idx)
    return result
