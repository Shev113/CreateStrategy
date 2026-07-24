import math
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timedelta

from intraday.strategies import SOLABUTO_REGISTRY, get_solabuto_defaults
from intraday.engine import IntradayEngine, H1_BARS_PER_YEAR
from core.session_store import get_cached_range, save_session, merge_candles, load_session
from core.moex_session import MOEX_SESSION

H1_INTERVAL = 60
H1_DAYS_LIMIT = 30
CANDLE_FIELDS = 8
MIN_CANDLES = 30


def _fetch_h1_data(ticker, start, end):
    cached = get_cached_range(ticker, 60, start, end)
    if cached is not None:
        return cached

    session = load_session(ticker, 60)
    if session is not None:
        s_last = session.get('last_date', '')
        s_start = session.get('start_date', '')
        try:
            last_dt = datetime.strptime(s_last, '%Y-%m-%d')
            end_dt = datetime.strptime(end, '%Y-%m-%d')
            start_dt = datetime.strptime(start, '%Y-%m-%d')
            c_start_dt = datetime.strptime(s_start, '%Y-%m-%d') if s_start else None

            need_tail = last_dt < end_dt
            need_head = c_start_dt and c_start_dt > start_dt

            if need_tail or need_head:
                result_candles = list(session['candles'])

                if need_tail:
                    tail_start = max(s_last, start)
                    tail = _fetch_h1_raw(ticker, tail_start, end)
                    if tail:
                        result_candles = merge_candles(result_candles, tail)

                if need_head:
                    head_end = min(s_start, end)
                    head = _fetch_h1_raw(ticker, start, head_end)
                    if head:
                        result_candles = merge_candles(head, result_candles)

                save_session(ticker, 60, result_candles, start_date=start)
                return result_candles

            return result_candles
        except ValueError:
            pass

    result = _fetch_h1_raw(ticker, start, end)
    if result:
        save_session(ticker, 60, result, start_date=start)
    return result


def _fetch_h1_raw(ticker, start, end):
    url = (f'https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR'
           f'/securities/{ticker}/candles.json')
    start_dt = datetime.strptime(start, '%Y-%m-%d')
    end_dt = datetime.strptime(end, '%Y-%m-%d')
    all_candles = []
    step = timedelta(days=H1_DAYS_LIMIT)
    cur = start_dt
    while cur < end_dt:
        nxt = min(cur + step, end_dt)
        params = {'from': cur.strftime('%Y-%m-%d'), 'till': nxt.strftime('%Y-%m-%d'), 'interval': H1_INTERVAL}
        try:
            resp = MOEX_SESSION.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if 'candles' in data and 'data' in data['candles']:
                all_candles.extend(data['candles']['data'])
        except Exception as e:
            logging.warning(f'H1 fetch failed for {ticker}: {e}')
        cur = nxt
    return all_candles if all_candles else None


def _calc_h1_composite(metrics, min_trades=5):
    trades = metrics.get('total_trades', 0)
    sharpe = metrics.get('sharpe', 0)
    ret = metrics.get('total_return', 0)
    if trades < min_trades:
        return -1.0
    if sharpe <= 0 and ret <= 0:
        return -1.0
    if sharpe > 0 and ret > 0:
        return sharpe * (ret / 100.0) * math.log2(max(trades, 2))
    if sharpe > 0:
        return sharpe * 0.1
    return ret * 0.01


def _build_h1_signal(trades, data):
    if not trades or not data:
        return {'action': 'NONE', 'level': None}
    last = trades[-1]
    return {
        'action': last.get('side', 'NONE'),
        'entry_price': last.get('entry_price', 0),
        'sl_price': last.get('sl_price', 0),
        'tp_price': last.get('tp_price', 0),
        'level': last.get('entry_price', 0),
        'last_price': float(data[-1][1]) if data[-1] else 0,
    }


class IntradaySmartScanner:
    def __init__(self, listing_levels=None):
        self.results = []
        self._listing_levels = listing_levels or {}

    def scan(self, tickers, date_from, date_to, base_params,
             min_trades=10, progress_fn=None):
        self.results = []
        if not tickers:
            return self.results

        strategy_ids = list(SOLABUTO_REGISTRY.keys())
        strategy_names = {k: v['name'] for k, v in SOLABUTO_REGISTRY.items()}
        total_processed = 0
        total_steps = len(tickers) * len(strategy_ids)
        base_defaults = get_solabuto_defaults('nr4')

        data_map = {}
        with ThreadPoolExecutor(max_workers=5) as pool:
            fut_to_ticker = {
                pool.submit(_fetch_h1_data, t, date_from, date_to): t
                for t in tickers
            }
            for f in as_completed(fut_to_ticker, timeout=120):
                t = fut_to_ticker[f]
                try:
                    result = f.result()
                    if result is not None and len(result) >= MIN_CANDLES:
                        data_map[t] = result
                except Exception:
                    pass

        for ticker in tickers:
            data = data_map.get(ticker)
            if data is None:
                total_processed += 1
                continue

            strategies_result = {}
            best_strategy_id = None
            best_score = -1.0

            for sid in strategy_ids:
                if progress_fn:
                    step = total_processed * len(strategy_ids) + strategy_ids.index(sid)
                    progress_fn(step, total_steps, ticker, strategy_names[sid])

                params = deepcopy(base_params)
                defaults = get_solabuto_defaults(sid)
                for k, v in defaults.items():
                    params.setdefault(k, v)
                strategy_params = dict(params)

                engine = IntradayEngine(
                    capital=params.get('capital', 1_000_000),
                    risk_per_trade=params.get('risk_per_trade', 0.02),
                    atr_sl=params.get('atr_sl', 1.0),
                    atr_tp=params.get('atr_tp', 2.0),
                    max_hold=params.get('max_hold', 20),
                    commission=params.get('commission', 0.0005),
                    entry_type=params.get('entry_type', 0),
                    strategy=sid,
                    level_proximity=params.get('level_proximity', 0.5),
                    dmk_gap_boost=params.get('dmk_gap_boost', 0),
                    shl_session_start=params.get('shl_session_start', 7),
                )

                try:
                    trades, metrics = engine.run(data)
                except Exception:
                    metrics = {}
                    trades = []

                score = _calc_h1_composite(metrics, min_trades)
                if score > best_score:
                    best_score = score
                    best_strategy_id = sid

                signal = _build_h1_signal(trades, data)
                strategies_result[sid] = {
                    'metrics': metrics,
                    'trades': trades,
                    'signal': signal,
                    'score': score,
                }

            entry = {
                'ticker': ticker,
                'strategies': strategies_result,
                'best_strategy': best_strategy_id,
                'best_score': best_score,
                'listing_level': self._listing_levels.get(ticker.upper()),
            }
            if best_strategy_id and best_strategy_id in strategies_result:
                s = strategies_result[best_strategy_id]
                entry['best_metrics'] = s['metrics']
                entry['best_signal'] = s['signal']
            else:
                entry['best_metrics'] = {}
                entry['best_signal'] = {'action': 'NONE'}
            self.results.append(entry)
            total_processed += 1

        self.results.sort(key=lambda r: r.get('best_score', -1), reverse=True)
        return self.results
