import json
import logging
import os
from datetime import datetime

from utils import app_dir

SIGNALS_PATH = os.path.join(app_dir(), 'results', 'signals.json')


class SignalStorage:
    def __init__(self, path=None):
        self._path = path or SIGNALS_PATH
        self._signals = []
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    self._signals = json.load(f)
            except Exception:
                self._signals = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(self._signals, f, ensure_ascii=False, indent=1)
        except Exception as e:
            logging.warning(f'Signal save error: {e}')

    def add_signal(self, ticker, side, price, strategy, sl=None, tp=None,
                   entered=False, date=None):
        signal = {
            'date': date or datetime.now().strftime('%Y-%m-%d %H:%M'),
            'ticker': ticker.upper(),
            'side': side,
            'price': round(float(price), 2) if price else None,
            'strategy': strategy,
            'sl': round(float(sl), 2) if sl else None,
            'tp': round(float(tp), 2) if tp else None,
            'entered': entered,
        }
        self._signals.append(signal)
        if len(self._signals) > 5000:
            self._signals = self._signals[-5000:]
        self._save()
        return signal

    def get_signals(self, ticker=None, strategy=None, side=None, limit=500):
        result = self._signals
        if ticker:
            result = [s for s in result if s['ticker'] == ticker.upper()]
        if strategy and strategy != 'Все':
            result = [s for s in result if s['strategy'] == strategy]
        if side and side != 'Все':
            result = [s for s in result if s['side'] == side]
        return result[-limit:]

    def get_strategies(self):
        return sorted(set(s['strategy'] for s in self._signals if s.get('strategy')))

    def export_csv(self, path, ticker=None, strategy=None, side=None):
        signals = self.get_signals(ticker=ticker, strategy=strategy, side=side,
                                    limit=10000)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                headers = ['date', 'ticker', 'side', 'price', 'strategy', 'sl', 'tp', 'entered']
                f.write(';'.join(headers) + '\n')
                for s in signals:
                    row = [
                        str(s.get('date', '')),
                        str(s.get('ticker', '')),
                        str(s.get('side', '')),
                        str(s.get('price', '') or ''),
                        str(s.get('strategy', '')),
                        str(s.get('sl', '') or ''),
                        str(s.get('tp', '') or ''),
                        'Да' if s.get('entered') else 'Нет',
                    ]
                    f.write(';'.join(row) + '\n')
            return len(signals)
        except Exception as e:
            logging.warning(f'Signal CSV export error: {e}')
            return 0
