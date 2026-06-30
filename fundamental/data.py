import json
import logging
import os
import threading
from datetime import datetime

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from utils import app_dir

_FUND_CACHE_PATH = os.path.join(app_dir(), 'results', 'fundamental_cache.json')

_TQBR_URL = 'https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities.json'
_DIVIDEND_URL = 'https://iss.moex.com/iss/securities/{ticker}/dividends.json'
_EMITTER_URL = 'https://iss.moex.com/iss/emitters/{emitter_id}.json'


def _fetch_json(url, params=None, timeout=20):
    try:
        r = requests.get(url, params=params or {}, timeout=timeout, verify=False)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.debug(f'Fundamental fetch error {url}: {e}')
        return None


def fetch_all_tqbr_fundamentals():
    data = _fetch_json(_TQBR_URL, params={
        'iss.meta': 'off',
        'iss.only': 'securities,marketdata',
    })
    if not data:
        return {}

    sec_cols = data.get('securities', {}).get('columns', [])
    sec_rows = data.get('securities', {}).get('data', [])
    md_cols = data.get('marketdata', {}).get('columns', [])
    md_rows = data.get('marketdata', {}).get('data', [])

    sec_idx = {c: i for i, c in enumerate(sec_cols)}
    md_idx = {c: i for i, c in enumerate(md_cols)}

    md_by_ticker = {}
    for row in md_rows:
        ticker = row[md_idx.get('SECID', 0)] if row else None
        if ticker:
            md_by_ticker[ticker] = row

    result = {}
    for row in sec_rows:
        ticker = row[sec_idx.get('SECID', 0)] if row else None
        if not ticker:
            continue

        prev_price = _safe_float(row, sec_idx, 'PREVPRICE')
        issue_size = _safe_float(row, sec_idx, 'ISSUESIZE')
        isin = _safe_str(row, sec_idx, 'ISIN')
        face_value = _safe_float(row, sec_idx, 'FACEVALUE')

        cap = None
        if ticker in md_by_ticker:
            cap = _safe_float(md_by_ticker[ticker], md_idx, 'ISSUECAPITALIZATION')

        eps = None
        if prev_price and issue_size and prev_price > 0 and issue_size > 0:
            shares = issue_size
            pass

        result[ticker] = {
            'ticker': ticker,
            'prev_price': prev_price,
            'issue_size': issue_size,
            'isin': isin,
            'face_value': face_value,
            'market_cap': cap,
        }

    return result


def fetch_dividends(ticker):
    data = _fetch_json(_DIVIDEND_URL.format(ticker=ticker), params={'iss.meta': 'off'})
    if not data or 'dividends' not in data:
        return []

    cols = data['dividends'].get('columns', [])
    rows = data['dividends'].get('data', [])
    idx = {c: i for i, c in enumerate(cols)}

    dividends = []
    for row in rows:
        date_val = _safe_str(row, idx, 'registryclosedate')
        value = _safe_float(row, idx, 'value')
        currency = _safe_str(row, idx, 'currencyid')
        if date_val and value:
            dividends.append({
                'date': date_val,
                'value': value,
                'currency': currency,
            })

    dividends.sort(key=lambda x: x['date'], reverse=True)
    return dividends


def calc_dividend_yield(dividends, price, months=12):
    if not dividends or not price or price <= 0:
        return None
    now = datetime.now()
    cutoff = None
    if months == 12:
        cutoff = f'{now.year - 1}-{now.month:02d}-{now.day:02d}'
    else:
        from dateutil.relativedelta import relativedelta
        try:
            cutoff_dt = now - relativedelta(months=months)
            cutoff = cutoff_dt.strftime('%Y-%m-%d')
        except Exception:
            cutoff = f'{now.year - 1}-{now.month:02d}-{now.day:02d}'

    total = sum(d['value'] for d in dividends if d['date'] >= cutoff)
    return round((total / price) * 100, 2)


def fetch_emitter_data(emitter_id):
    data = _fetch_json(_EMITTER_URL.format(emitter_id=emitter_id), params={'iss.meta': 'off'})
    if not data or 'emitter' not in data:
        return {}
    cols = data['emitter'].get('columns', [])
    rows = data['emitter'].get('data', [])
    if not rows:
        return {}
    idx = {c: i for i, c in enumerate(cols)}
    row = rows[0]
    return {
        'capitalization': _safe_float(row, idx, 'CAPITALIZATION'),
        'emitter_capitalization': _safe_float(row, idx, 'EMITTER_CAPITALIZATION'),
    }


def get_ticker_emitter_id(ticker):
    data = _fetch_json(
        'https://iss.moex.com/iss/securities/{ticker}.json'.format(ticker=ticker),
        params={'iss.meta': 'off', 'iss.only': 'description'}
    )
    if not data or 'description' not in data:
        return None
    cols = data['description'].get('columns', [])
    rows = data['description'].get('data', [])
    idx = {c: i for i, c in enumerate(cols)}
    for row in rows:
        name = _safe_str(row, idx, 'name')
        if name == 'EMITTER_ID':
            val = row[idx['value']] if 'value' in idx and idx['value'] < len(row) else None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None
    return None


def compute_fundamental_summary(ticker, price=None):
    result = {
        'ticker': ticker,
        'price': None,
        'market_cap': None,
        'shares': None,
        'div_yield': None,
        'dividends': [],
        'last_div': None,
        'pe': None,
        'pb': None,
        'eps': None,
        'book_value': None,
    }

    all_data = fetch_all_tqbr_fundamentals()
    ticker_data = all_data.get(ticker, {})
    result['price'] = price or ticker_data.get('prev_price')
    result['market_cap'] = ticker_data.get('market_cap')
    result['shares'] = ticker_data.get('issue_size')

    dividends = fetch_dividends(ticker)
    result['dividends'] = dividends
    if dividends:
        result['last_div'] = dividends[0] if dividends else None
        div_yield = calc_dividend_yield(dividends, result['price'])
        if div_yield is not None:
            result['div_yield'] = div_yield

    return result


def fetch_fundamental_batch(tickers, on_complete=None):
    def task():
        try:
            all_data = fetch_all_tqbr_fundamentals()
            results = {}
            for ticker in tickers:
                td = all_data.get(ticker)
                if not td:
                    continue
                dividends = fetch_dividends(ticker)
                price = td.get('prev_price')
                div_yield = calc_dividend_yield(dividends, price) if dividends and price else None
                results[ticker] = {
                    'ticker': ticker,
                    'price': price,
                    'market_cap': td.get('market_cap'),
                    'shares': td.get('issue_size'),
                    'div_yield': div_yield,
                    'last_div': dividends[0] if dividends else None,
                    'div_count': len(dividends),
                }
            return results
        except Exception as e:
            logging.warning(f'Fundamental batch error: {e}')
            return {}

    if on_complete is None:
        return task()

    def run():
        r = task()
        try:
            on_complete(r)
        except Exception:
            logging.warning('on_complete callback error in fetch_fundamental_batch')

    threading.Thread(target=run, daemon=True).start()


def format_fundamental_report(data):
    if not data:
        return 'Нет данных'

    lines = []
    lines.append(f"{'=' * 45}")
    lines.append(f"  ФУНДАМЕНТАЛЬНЫЙ АНАЛИЗ: {data.get('ticker', '—')}")
    lines.append(f"{'=' * 45}")
    lines.append('')

    if data.get('price'):
        lines.append(f"  Цена:             {data['price']:.2f} руб.")

    if data.get('market_cap'):
        mc = data['market_cap']
        if mc >= 1e12:
            lines.append(f"  Капитализация:    {mc / 1e12:.2f} трлн руб.")
        elif mc >= 1e9:
            lines.append(f"  Капитализация:    {mc / 1e9:.1f} млрд руб.")
        else:
            lines.append(f"  Капитализация:    {mc:,.0f} руб.")

    if data.get('shares'):
        s = data['shares']
        if s >= 1e9:
            lines.append(f"  Кол-во акций:     {s / 1e9:.2f} млрд")
        else:
            lines.append(f"  Кол-во акций:     {s:,.0f}")

    if data.get('eps') is not None:
        lines.append(f"  EPS:              {data['eps']:.2f} руб.")

    if data.get('pe') is not None:
        lines.append(f"  P/E:              {data['pe']:.1f}")

    if data.get('pb') is not None:
        lines.append(f"  P/B:              {data['pb']:.2f}")

    if data.get('div_yield') is not None:
        lines.append(f"  Див. доходность:  {data['div_yield']:.2f}%")

    if data.get('last_div'):
        ld = data['last_div']
        lines.append(f"  Посл. дивиденд:   {ld['value']:.2f} руб. ({ld['date']})")

    divs = data.get('dividends', [])
    if divs:
        lines.append('')
        lines.append(f"{'─' * 45}")
        lines.append(f"  ИСТОРИЯ ДИВИДЕНДОВ")
        lines.append(f"{'─' * 45}")
        for d in divs[:10]:
            lines.append(f"    {d['date']}   {d['value']:>8.2f} руб.")
        if len(divs) > 10:
            lines.append(f"    ... и ещё {len(divs) - 10} выплат")

    lines.append(f"\n{'=' * 45}")
    return '\n'.join(lines)


def format_fundamental_brief(data):
    if not data:
        return ''
    parts = []
    if data.get('pe') is not None:
        parts.append(f"P/E {data['pe']:.1f}")
    if data.get('div_yield') is not None:
        parts.append(f"Див {data['div_yield']:.1f}%")
    if data.get('market_cap'):
        mc = data['market_cap']
        if mc >= 1e12:
            parts.append(f"Кап {mc / 1e12:.1f}T")
        elif mc >= 1e9:
            parts.append(f"Кап {mc / 1e9:.0f}M")
    return '  |  '.join(parts) if parts else ''


def _safe_float(row, idx, key):
    try:
        i = idx.get(key)
        if i is not None and i < len(row) and row[i] is not None:
            return float(row[i])
    except (ValueError, TypeError):
        pass
    return None


def _safe_str(row, idx, key):
    try:
        i = idx.get(key)
        if i is not None and i < len(row) and row[i] is not None:
            return str(row[i])
    except Exception:
        pass
    return ''
