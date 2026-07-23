# scanner.py
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .sectors import SectorDB
from .levels_strength import DEFAULT_LAST_CANDLES, calculate_level_strength, get_best_level_signal, WAIT_ACTION
from utils import normalize_numeric_params

from strategy.indicators import calc_atr
from backtest.engine import BacktestEngine, candles_to_df


class Scanner:
    def __init__(self, sector_db=None, fetch_fn=None):
        self.sector_db = sector_db or SectorDB()
        self.fetch_fn = fetch_fn
        self.results = []
        self.ticker_overrides_used = set()

    def _fetch_ticker_data(self, ticker, date_from, date_to):
        try:
            stock_data = self.fetch_fn(ticker, date_from, date_to)
            if isinstance(stock_data, str) or not isinstance(stock_data, list):
                return None
            if len(stock_data) < 30:
                return None
            return stock_data
        except Exception:
            return None

    def _load_ticker_overrides(self, ticker, ticker_settings_path):
        if not ticker_settings_path or not os.path.exists(ticker_settings_path):
            return None
        try:
            with open(ticker_settings_path, 'r', encoding='utf-8') as f:
                all_settings = json.load(f)
            return all_settings.get(ticker)
        except Exception:
            return None

    def _backtest_ticker(self, ticker, stock_data, backtest_params, ticker_settings_path):
        params = dict(backtest_params)
        has_override = False
        saved = self._load_ticker_overrides(ticker, ticker_settings_path)
        if saved:
            has_override = True
            if 'strategy' in saved:
                params['strategy'] = saved['strategy']
            if 'params' in saved:
                normalized = normalize_numeric_params(saved['params'])
                for k, v in normalized.items():
                    params[k] = v
            if 'risk_per_trade' in params:
                params['risk_per_trade'] = params['risk_per_trade'] / 100.0
            if 'commission' in params:
                params['commission'] = params['commission'] / 100.0

        if has_override:
            self.ticker_overrides_used.add(ticker)

        known_params = {'capital', 'risk_per_trade', 'atr_period', 'atr_sl', 'atr_tp',
                        'min_hits', 'max_hold', 'commission', 'tolerance', 'strategy'}
        strategy_kwargs = {k: v for k, v in params.items()
                           if k not in known_params}

        engine = BacktestEngine(
            strategy=params.get('strategy', 'bounce'),
            capital=params.get('capital', 1_000_000),
            risk_per_trade=params.get('risk_per_trade', 0.02),
            atr_sl=params.get('atr_sl', 1.0),
            atr_tp=params.get('atr_tp', 2.0),
            min_hits=params.get('min_hits', 5),
            max_hold=params.get('max_hold', 20),
            commission=params.get('commission', 0.0005),
            **strategy_kwargs
        )

        try:
            trades, metrics = engine.run(stock_data)
        except Exception:
            return None

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

            last_candles = DEFAULT_LAST_CANDLES
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

        return {
            'ticker': ticker,
            'trades': trades or [],
            'metrics': metrics,
            'signal': levels_signal,
            'last_price': last_price,
            'atr': atr_value,
        }

    def scan(self, sectors, date_from, date_to, backtest_params,
             ticker_settings_path=None, progress_fn=None):
        self.results = []
        all_tickers = self.sector_db.get_tickers(sectors)

        if not all_tickers:
            return self.results

        sector_list = [s for s in sectors if s in self.sector_db.get_all_sectors()]
        fetch_fn = self.fetch_fn

        ticker_to_sector = {}
        for sector in sector_list:
            for t in self.sector_db.get_tickers([sector]):
                if t not in ticker_to_sector:
                    ticker_to_sector[t] = sector

        tickers = list(ticker_to_sector.keys())
        data_map = {}

        with ThreadPoolExecutor(max_workers=5) as pool:
            fut_to_ticker = {
                pool.submit(self._fetch_ticker_data, t, date_from, date_to): t
                for t in tickers
            }
            for f in as_completed(fut_to_ticker):
                ticker = fut_to_ticker[f]
                try:
                    result = f.result()
                    if result is not None:
                        data_map[ticker] = result
                except Exception:
                    pass

        total = len(tickers)
        processed = 0
        for ticker in tickers:
            if ticker not in data_map:
                processed += 1
                continue

            if progress_fn:
                progress_fn(processed, total, ticker, ticker_to_sector[ticker])

            entry = self._backtest_ticker(ticker, data_map[ticker], backtest_params, ticker_settings_path)
            if entry is not None:
                entry['sector'] = ticker_to_sector[ticker]
                entry['listing_level'] = self.sector_db.get_listing_level(ticker)
                self.results.append(entry)

            processed += 1

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
