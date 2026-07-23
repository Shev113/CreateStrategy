import logging
import math
import time
import traceback
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool

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


def _run_ticker_strategies(stock_data, base_params, min_trades, strategy_ids,
                            ticker=''):
    """Module-level worker for ProcessPoolExecutor. Runs all strategies for one ticker."""
    try:
        logger = logging.getLogger(__name__)
        try:
            df = candles_to_df(stock_data)
        except Exception as e:
            logger.exception('SmartScanner: %s candles_to_df failed: %s', ticker, e)
            df = None
        atr_series = None
        if df is not None and len(df) > 0:
            try:
                atr_period = base_params.get('atr_period', 14)
                atr_series = calc_atr(df, atr_period)
            except Exception as e:
                logger.exception('SmartScanner: %s calc_atr failed: %s', ticker, e)

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
                atr_period=params.get('atr_period', 14),
                _precomputed_atr=atr_series,
            )
            try:
                trades, metrics = engine.run(stock_data)
            except Exception as e:
                logger.exception('SmartScanner: %s/%s engine.run failed: %s', ticker, sid, e)
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
        return results
    except Exception:
        tb = traceback.format_exc()
        return {'__error__': f'{ticker}: {tb}'}


class SmartScanner:
    def __init__(self, sector_db=None, fetch_fn=None):
        self.sector_db = sector_db or SectorDB()
        self.fetch_fn = fetch_fn
        self.results = []

    def scan(self, sectors, date_from, date_to, base_params,
             min_trades=30, progress_fn=None, strategy_ids=None):
        self.results = []
        all_tickers = self.sector_db.get_tickers(sectors)
        if not all_tickers:
            return self.results

        sector_list = [s for s in sectors if s in self.sector_db.get_all_sectors()]

        if strategy_ids:
            strategy_ids = [s for s in strategy_ids if s in STRATEGY_REGISTRY]
        if not strategy_ids:
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
        logging.info(f'SmartScanner: Phase 1 — fetching {total_tickers} tickers')
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

        # Phase 2: collect tickers with data (df/atr computed inside worker)
        ticker_prepared = []
        for t in tickers:
            sd = data_map.get(t)
            if sd is None:
                continue
            ticker_prepared.append((t, sd))

        # Phase 3: run strategies for all tickers in parallel (CPU bound)
        total_processed = 0
        skipped_count = total_tickers - len(ticker_prepared)
        logging.info(f'SmartScanner: Phase 2 done — {len(ticker_prepared)} tickers prepared, {skipped_count} skipped')

        with ProcessPoolExecutor(max_workers=min(4, len(ticker_prepared) or 1)) as pool:
            fut_map = {}
            for t, sd in ticker_prepared:
                fut = pool.submit(_run_ticker_strategies, sd, base_params,
                                  min_trades, strategy_ids, t)
                fut_map[fut] = t

            logging.info(f'SmartScanner: Phase 3 — started {len(fut_map)} workers')
            progress_start = time.monotonic()
            total_processed_tickers = 0

            for f in as_completed(fut_map):
                t = fut_map[f]
                try:
                    strategies_result = f.result()
                except BrokenProcessPool:
                    logging.error('SmartScanner: ProcessPoolExecutor broken, aborting')
                    break
                except Exception as e:
                    logging.exception(f'SmartScanner: {t} worker failed: {e}')
                    strategies_result = {}
                if '__error__' in strategies_result:
                    logging.error(f'SmartScanner: {t} worker error:\n{strategies_result["__error__"]}')
                    strategies_result = {}

                total_processed_tickers += 1
                if progress_fn:
                    elapsed = time.monotonic() - progress_start
                    rate = total_processed_tickers / elapsed if elapsed > 0 else 0
                    remaining = (total_tickers - total_processed_tickers) / rate if rate > 0 else 0
                    if remaining >= 60:
                        eta_str = f"~{int(remaining // 60)}:{int(remaining % 60):02d}"
                    else:
                        eta_str = f"~{int(remaining)}с"
                    step = total_processed_tickers * len(strategy_ids)
                    progress_fn(min(step, total_steps), total_steps, t, eta_str)

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
                    'listing_level': self.sector_db.get_listing_level(t),
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


