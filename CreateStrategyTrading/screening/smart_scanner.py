# smart_scanner.py
import math
from copy import deepcopy

from .sectors import SectorDB
from .levels_strength import DEFAULT_LAST_CANDLES, calculate_level_strength, get_best_level_signal

from strategy.config import STRATEGY_REGISTRY
from strategy.indicators import calc_atr
from backtest.engine import BacktestEngine, candles_to_df


def calc_composite(metrics, min_trades=30):
    trades = metrics.get('total_trades', 0)
    sharpe = metrics.get('sharpe', 0)
    ret = metrics.get('total_return', 0)
    if trades < min_trades or sharpe <= 0 or ret <= 0:
        return -1.0
    return sharpe * (ret / 100.0) * math.log2(trades)


def _calc_signal(trades, stock_data, params):
    if not trades or not stock_data:
        return {'action': 'NONE', 'level': None, 'strength': None}
    try:
        last_price = float(stock_data[-1][1])
        df = candles_to_df(stock_data)
        if df is None or len(df) == 0:
            return {'action': 'NONE', 'level': None, 'strength': None}
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

        total_processed = 0
        total_tickers = len(all_tickers)
        total_steps = total_tickers * len(strategy_ids)

        for sector in sector_list:
            tickers_in_sector = self.sector_db.get_tickers([sector])
            if not tickers_in_sector:
                continue

            for ticker in tickers_in_sector:
                try:
                    stock_data = self.fetch_fn(ticker, date_from, date_to)
                    if isinstance(stock_data, str) or not isinstance(stock_data, list):
                        total_processed += 1
                        continue
                    if len(stock_data) < 30:
                        total_processed += 1
                        continue
                except Exception:
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
                    )

                    try:
                        trades, metrics = engine.run(stock_data)
                    except Exception:
                        metrics = {}
                        trades = []

                    score = calc_composite(metrics, min_trades)
                    if score > best_score:
                        best_score = score
                        best_strategy_id = sid

                    signal = _calc_signal(trades, stock_data, params)

                    strategies_result[sid] = {
                        'metrics': metrics,
                        'trades': trades,
                        'signal': signal,
                        'score': score,
                    }

                entry = {
                    'ticker': ticker,
                    'sector': sector,
                    'strategies': strategies_result,
                    'best_strategy': best_strategy_id,
                    'best_score': best_score,
                }
                entry.update(self._best_info(strategies_result, best_strategy_id))
                self.results.append(entry)
                total_processed += 1

        self.results.sort(key=lambda r: r.get('best_score', -1), reverse=True)
        return self.results

    def _best_info(self, strategies, best_id):
        if not best_id or best_id not in strategies:
            return {'best_metrics': {}, 'best_signal': {'action': 'NONE'}}
        s = strategies[best_id]
        return {
            'best_metrics': s['metrics'],
            'best_signal': s['signal'],
        }
