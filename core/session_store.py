import json
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from utils import app_dir

_SESSIONS_DIR = os.path.join(app_dir(), 'results', 'candles')
_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(_SESSIONS_DIR, exist_ok=True)


def _file_path(ticker: str, tf: int) -> str:
    return os.path.join(_SESSIONS_DIR, f'{ticker}_{tf}.json')


def _parse_date(candle) -> Optional[str]:
    if candle is None or not isinstance(candle, (list, tuple)):
        return None
    for idx in (6, 7, 0):
        if len(candle) > idx:
            val = candle[idx]
            if isinstance(val, str) and len(val) >= 10:
                return val
    return None


def load_session(ticker: str, tf: int) -> Optional[dict]:
    path = _file_path(ticker, tf)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        candles = data.get('candles', [])
        if not candles:
            return None
        if not isinstance(candles, list):
            return None
        first_date = _parse_date(candles[0])
        last_date = _parse_date(candles[-1])
        if not last_date:
            return None
        if first_date:
            first_date = first_date[:10]
        if last_date:
            last_date = last_date[:10]
        return {
            'ticker': ticker,
            'tf': tf,
            'start_date': data.get('start_date', first_date or ''),
            'last_date': last_date,
            'candles': candles,
        }
    except Exception as e:
        logging.debug(f'SessionStore load error {ticker}_{tf}: {e}')
        return None


def save_session(ticker: str, tf: int, candles: list, start_date: str = ''):
    if not candles:
        return
    _ensure_dir()
    first_date = _parse_date(candles[0])
    last_date = _parse_date(candles[-1])
    if first_date:
        first_date = first_date[:10]
    if last_date:
        last_date = last_date[:10]
    data = {
        'ticker': ticker,
        'tf': tf,
        'start_date': first_date,
        'last_date': last_date,
        'candles': candles,
    }
    path = _file_path(ticker, tf)
    try:
        with _lock:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logging.debug(f'SessionStore save error {ticker}_{tf}: {e}')


def merge_candles(existing: list, delta: list) -> list:
    if not existing:
        return delta
    if not delta:
        return existing

    existing_keys = set()
    for c in existing:
        d = _parse_date(c)
        if d:
            existing_keys.add(d)

    merged = list(existing)
    for c in delta:
        d = _parse_date(c)
        if d and d not in existing_keys:
            merged.append(c)
            existing_keys.add(d)

    def _sort_key(c):
        d = _parse_date(c)
        if d:
            return d
        return ''

    merged.sort(key=_sort_key)
    return merged


def get_delta_range(ticker: str, tf: int, requested_start: str, requested_end: str) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
    session = load_session(ticker, tf)
    if session is None:
        return requested_start, requested_end, None

    cached_start = session.get('start_date', '')
    cached_last = session.get('last_date', '')

    try:
        req_start = datetime.strptime(requested_start, '%Y-%m-%d')
        req_end = datetime.strptime(requested_end, '%Y-%m-%d')
        c_last = datetime.strptime(cached_last, '%Y-%m-%d') if cached_last else None
        c_start = datetime.strptime(cached_start, '%Y-%m-%d') if cached_start else None
    except ValueError:
        return requested_start, requested_end, session

    fetch_start = requested_start
    fetch_end = requested_end
    need_fetch = False

    if c_last and c_last < req_end:
        fetch_start = max(cached_last, requested_start)
        need_fetch = True

    if c_start and c_start > req_start:
        fetch_end = min(cached_start, requested_end)
        need_fetch = True
    elif not need_fetch:
        if c_last >= req_end and c_start <= req_start:
            return None, None, session
        fetch_start = requested_start
        fetch_end = requested_end

    if not need_fetch:
        return None, None, session

    return fetch_start, fetch_end, session


def get_cached_range(ticker: str, tf: int, start: str, end: str) -> Optional[list]:
    session = load_session(ticker, tf)
    if session is None:
        return None

    try:
        req_start = datetime.strptime(start, '%Y-%m-%d')
        req_end = datetime.strptime(end, '%Y-%m-%d')
        c_start = datetime.strptime(session.get('start_date', ''), '%Y-%m-%d')
        c_last = datetime.strptime(session.get('last_date', ''), '%Y-%m-%d')
    except (ValueError, TypeError):
        return None

    if c_start <= req_start and c_last >= req_end:
        filtered = []
        for c in session['candles']:
            d = _parse_date(c)
            if d:
                dt_str = d[:10]
                try:
                    dt = datetime.strptime(dt_str, '%Y-%m-%d')
                except ValueError:
                    continue
                if req_start <= dt <= req_end:
                    filtered.append(c)
        return filtered if filtered else None

    return None
