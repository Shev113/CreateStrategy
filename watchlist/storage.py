import json
import logging
import os
import threading

from utils import app_dir

WATCHLIST_PATH = os.path.join(app_dir(), 'results', 'watchlist.json')


class WatchlistStorage:
    def __init__(self, path=None):
        self._path = path or WATCHLIST_PATH
        self._tickers = []
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    self._tickers = json.load(f)
            except Exception:
                self._tickers = []

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(self._tickers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning(f'Watchlist save error: {e}')

    def get_tickers(self):
        return list(self._tickers)

    def add(self, ticker):
        ticker = ticker.strip().upper()
        if ticker and ticker not in self._tickers:
            self._tickers.append(ticker)
            self._save()
            return True
        return False

    def remove(self, ticker):
        ticker = ticker.strip().upper()
        if ticker in self._tickers:
            self._tickers.remove(ticker)
            self._save()
            return True
        return False

    def reorder(self, new_order):
        self._tickers = [t for t in new_order if t in self._tickers]
        self._save()
