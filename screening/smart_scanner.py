import logging
import math
import multiprocessing as mp
import threading
import time
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

from .sectors import SectorDB
from .levels_strength import DEFAULT_LAST_CANDLES, calculate_level_strength, get_best_level_signal

from strategy.config import STRATEGY_REGISTRY
from strategy.indicators import calc_atr
from backtest.engine import BacktestEngine, candles_to_df


def calc_composite(metrics, min_trades=30):
    trades = metrics.get('total_trades', 0)
    sharpe = metrics.get('sharpe', 0)
    ret = metrics.get('total_return', 0)
    if trades < min_trades:
        return -1.0
    if sharpe <= 0 and ret <= 0:
        return -1.0
    if sharpe > 0 and ret > 0:
        return sharpe * (ret / 100.0) * math.log2(trades)
    if sharpe > 0:
        return sharpe * 0.1
    return ret * 0.01


def _calc_signal(trades, stock_data, params, _precomputed_atr_series=None, _precomputed_df=None):
    if not trades or not stock_data:
        return {'action': 'NONE', 'level': None, 'strength': None}
    try:
        last_price = float(stock_data[-1][1])
        df = _precomputed_df
        if df is None:
            df = candles_to_df(stock_data)
        if df is None or len(df) == 0:
            return {'action': 'NONE', 'level': None, 'strength': None}
        atr_series = _precomputed_atr_series
        if atr_series is None:
            atr_series = calc_atr(df, params.get('atr_period', 14))
        if atr_series.empty or atr_series.isna().iloc[-1]:
            return {'action': 'NONE', 'level': None, 'strength': None}
        atr_value = atr_series.iloc[-1]
        levels_strength = calculate_level_strength(trades, last_candles=DEFAULT_LAST_CANDLES)
        if not levels_strength:
            return {'action': 'NONE', 'level': None, 'strength': None}
        atr_sl_val = params.get('atr_sl', 1.0)
        atr_tp_val = params.get('atr_tp', 2.0)
        signal = get_best_level_signal(levels_strength, last_price, atr_value,
                                       atr_sl=atr_sl_val, atr_tp=atr_tp_val)
        if signal and signal['action'] == 'NONE':
            signal = get_best_level_signal(levels_strength, last_price, atr_value,
                                           threshold_mult=1.0, atr_sl=atr_sl_val, atr_tp=atr_tp_val)
        if signal:
            signal['last_price'] = last_price
            signal['atr'] = atr_value
        return signal or {'action': 'NONE', 'level': None, 'strength': None}
    except Exception:
        return {'action': 'NONE', 'level': None, 'strength': None}


def _run_ticker_strategies(stock_data, base_params, min_trades, atr_series, df, strategy_ids,
                            ticker='', progress_queue=None):
    """Module-level worker for ProcessPoolExecutor. Runs all strategies for one ticker."""
    results = {}
    for sid in strategy_ids:
        params = deepcopy(base_params)
        engine = BacktestEngine(
            strategy=sid,
            capital=params.get('capital', 1_000_000),
            risk_per_trade=params.get('risk_per_trade', 0.02),
            atr_sl=params.get('atr_sl', 1.0),
            atr_tp=params.get('atr_tp', 2.0),
            min_hits=params.get('min_hits', 5),
            max_hold=params.get('max_hold', 20),
            commission=params.get('commission', 0.0005),
            entry_type=params.get('entry_type', 0),
            _precomputed_atr=atr_series,
        )
        try:
            trades, metrics = engine.run(stock_data)
        except Exception:
            metrics = {}
            trades = []
        score = calc_composite(metrics, min_trades)
        signal = _calc_signal(trades, stock_data, params,
                              _precomputed_atr_series=atr_series,
                              _precomputed_df=df)
        results[sid] = {
            'metrics': metrics,
            'trades': trades,
            'signal': signal,
            'score': score,
        }
        if progress_queue is not None:
            progress_queue.put(ticker)
    return results


class SmartScanner:
    def __init__(self, sector_db=None, fetch_fn=None):
        self.sector_db = sector_db or SectorDB()
        self.fetch_fn = fetch_fn
        self.results = []

    def scan(self, sectors, date_from, date_to, base_params,
             min_trades=30, progress_fn=None):
        self.results = []
        all_tickers = self.sector_db.get_tickers(sectors)
        if not all_tickers:
            return self.results

        sector_list = [s for s in sectors if s in self.sector_db.get_all_sectors()]
        strategy_ids = list(STRATEGY_REGISTRY.keys())
        strategy_names = {k: v['name'] for k, v in STRATEGY_REGISTRY.items()}

        ticker_to_sector = {}
        for sector in sector_list:
            for t in self.sector_db.get_tickers([sector]):
                if t not in ticker_to_sector:
                    ticker_to_sector[t] = sector

        tickers = list(ticker_to_sector.keys())
        total_tickers = len(tickers)
        total_steps = total_tickers * len(strategy_ids)

        # Phase 1: fetch all data in parallel (I/O bound)
        data_map = {}
        with ThreadPoolExecutor(max_workers=5) as pool:
            def _fetch(t):
                try:
                    d = self.fetch_fn(t, date_from, date_to)
                    if isinstance(d, list) and len(d) >= 30:
                        return t, d
                except Exception:
                    pass
                return t, None
            fut_map = {pool.submit(_fetch, t): t for t in tickers}
            for f in as_completed(fut_map):
                t, d = f.result()
                if d is not None:
                    data_map[t] = d

        # Phase 2: build df + atr for each ticker (fast, in main process)
        ticker_prepared = []
        for t in tickers:
            sd = data_map.get(t)
            if sd is None:
                continue
            df = candles_to_df(sd)
            atr_series = None
            if df is not None and len(df) > 0:
                atr_series = calc_atr(df, base_params.get('atr_period', 14))
            ticker_prepared.append((t, sd, atr_series, df))

        # Phase 3: run strategies for all tickers in parallel (CPU bound)
        total_processed = 0
        skipped_count = total_tickers - len(ticker_prepared)

        # Per-strategy progress via mp.Queue (worker sends ticker per strategy done)
        progress_queue = mp.Queue() if progress_fn else None
        _progress_step = 0

        def _drain():
            nonlocal _progress_step
            if not progress_fn:
                return
            start = time.monotonic()
            while _progress_step < total_steps:
                try:
                    ticker_name = progress_queue.get()
                    _progress_step += 1
                    elapsed = time.monotonic() - start
                    rate = _progress_step / elapsed if elapsed > 0 else 0
                    remaining = (total_steps - _progress_step) / rate if rate > 0 else 0
                    if remaining >= 60:
                        eta_str = f"~{int(remaining // 60)}:{int(remaining % 60):02d}"
                    else:
                        eta_str = f"~{int(remaining)}с"
                    progress_fn(min(_progress_step, total_steps), total_steps, ticker_name, eta_str)
                except Exception:
                    break

        if progress_queue is not None:
            threading.Thread(target=_drain, daemon=True).start()

        with ProcessPoolExecutor(max_workers=min(6, len(ticker_prepared) or 1)) as pool:
            fut_map = {}
            for t, sd, atr_series, df in ticker_prepared:
                fut = pool.submit(_run_ticker_strategies, sd, base_params,
                                  min_trades, atr_series, df, strategy_ids,
                                  t, progress_queue)
                fut_map[fut] = (t, sd, atr_series, df)

            for f in as_completed(fut_map):
                t, sd, atr_series, df = fut_map[f]
                try:
                    strategies_result = f.result()
                except Exception as e:
                    logging.warning(f'SmartScanner: {t} process worker failed: {e}')
                    strategies_result = {}

                best_strategy_id = None
                best_score = -1.0
                for sid, res in strategies_result.items():
                    if res['score'] > best_score:
                        best_score = res['score']
                        best_strategy_id = sid

                sector = ticker_to_sector.get(t, '')
                entry = {
                    'ticker': t,
                    'sector': sector,
                    'strategies': strategies_result,
                    'best_strategy': best_strategy_id,
                    'best_score': best_score,
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

        logging.info(f'SmartScanner: done. tested={len(self.results)} skipped={skipped_count} of {total_tickers}')
        self.results.sort(key=lambda r: r.get('best_score', -1), reverse=True)
        self.skipped_count = skipped_count
        return self.results

    def _best_info(self, strategies, best_id):
        if not best_id or best_id not in strategies:
            return {'best_metrics': {}, 'best_signal': {'action': 'NONE'}}
        s = strategies[best_id]
        return {
            'best_metrics': s['metrics'],
            'best_signal': s['signal'],
        }
