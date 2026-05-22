# scanner.py
import time
from datetime import datetime

from .sectors import SectorDB
from .levels_strength import calculate_level_strength, get_best_level_signal, WAIT_ACTION

from strategy.indicators import calc_atr
from backtest.engine import BacktestEngine, candles_to_df


class Scanner:
    def __init__(self, sector_db=None, fetch_fn=None):
        self.sector_db = sector_db or SectorDB()
        self.fetch_fn = fetch_fn
        self.results = []

    def scan(self, sectors, date_from, date_to, backtest_params, progress_fn=None):
        """
        Run backtest for all tickers in given sectors.

        backtest_params: {capital, risk_per_trade, atr_sl, atr_tp, min_hits, ...}
        progress_fn(current, total, ticker, sector)
        """
        self.results = []
        all_tickers = self.sector_db.get_tickers(sectors)

        if not all_tickers:
            return self.results

        sector_list = [s for s in sectors if s in self.sector_db.get_all_sectors()]
        fetch_fn = self.fetch_fn

        total_processed = 0
        for sector in sector_list:
            tickers_in_sector = self.sector_db.get_tickers([sector])
            if not tickers_in_sector:
                continue

            for t_idx, ticker in enumerate(tickers_in_sector):
                if progress_fn:
                    progress_fn(total_processed, len(all_tickers), ticker, sector)

                try:
                    stock_data = fetch_fn(ticker, date_from, date_to)
                    if isinstance(stock_data, str) or not isinstance(stock_data, list):
                        total_processed += 1
                        continue
                    if len(stock_data) < 30:
                        total_processed += 1
                        continue
                except Exception:
                    total_processed += 1
                    continue

                engine = BacktestEngine(
                    capital=backtest_params.get('capital', 1_000_000),
                    risk_per_trade=backtest_params.get('risk_per_trade', 0.02),
                    atr_sl=backtest_params.get('atr_sl', 1.0),
                    atr_tp=backtest_params.get('atr_tp', 2.0),
                    min_hits=backtest_params.get('min_hits', 5),
                    max_hold=backtest_params.get('max_hold', 20),
                    commission=backtest_params.get('commission', 0.0005)
                )

                try:
                    trades, metrics = engine.run(stock_data)
                except Exception:
                    total_processed += 1
                    continue

                last_price = None
                atr_value = None
                levels_signal = {'action': 'NONE', 'level': None, 'strength': None}

                if trades:
                    df = candles_to_df(stock_data)
                    if df is not None and len(df) > 0:
                        last_price = float(stock_data[-1][1])
                        atr_series = calc_atr(df, 14)
                        if not atr_series.empty and not atr_series.isna().iloc[-1]:
                            atr_value = atr_series.iloc[-1]

                    last_candles = backtest_params.get('last_candles', 10)
                    levels_strength = calculate_level_strength(trades, last_candles=last_candles)
                    if levels_strength and atr_value and last_price:
                        atr_sl = backtest_params.get('atr_sl', 1.0)
                        atr_tp = backtest_params.get('atr_tp', 2.0)
                        levels_signal = get_best_level_signal(
                            levels_strength, last_price, atr_value,
                            atr_sl=atr_sl, atr_tp=atr_tp
                        )
                        if levels_signal['action'] == 'NONE':
                            levels_signal = get_best_level_signal(
                                levels_strength, last_price, atr_value,
                                threshold_mult=1.0, atr_sl=atr_sl, atr_tp=atr_tp
                            )
                elif metrics.get('total_trades', 0) > 0:
                    pass

                self.results.append({
                    'ticker': ticker,
                    'sector': sector,
                    'trades': trades or [],
                    'metrics': metrics,
                    'signal': levels_signal,
                    'last_price': last_price,
                    'atr': atr_value,
                })

                total_processed += 1

        self.results.sort(
            key=lambda r: r['metrics'].get('total_return', 0) if r['metrics'].get('sharpe', 0) > 0 else -999,
            reverse=True
        )

        return self.results

    def get_top(self, n=5):
        ranked = [r for r in self.results if r['signal']['action'] != 'NONE'
                  and r['metrics'].get('total_trades', 0) >= 3
                  and r['metrics'].get('sharpe', 0) > 0]
        ranked.sort(key=lambda r: r['metrics'].get('total_return', -999), reverse=True)
        return ranked[:n]
