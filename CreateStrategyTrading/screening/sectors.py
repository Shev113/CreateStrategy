import json
import logging
import os
import threading
import time

SECTORS_PATH = os.path.join(os.path.dirname(__file__), 'sectors.json')
CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'results', 'moex_sectors_cache.json')
CACHE_TTL = 86400
CACHE_VERSION = 2


class SectorDB:
    def __init__(self, path=None):
        self._ticker_to_sector = {}
        self._sector_to_tickers = {}
        self._load(path or SECTORS_PATH)

    def _load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        for sector, tickers in raw.items():
            upper = [t.upper() for t in tickers]
            self._sector_to_tickers[sector] = upper
            for t in upper:
                self._ticker_to_sector[t] = sector

    def load_dynamic_async(self, on_complete=None):
        """Fetch MOEX sector indices in background thread.
        on_complete(ticker_to_sector, sector_to_tickers) is called
        in the main thread when done (or None, None on failure).
        """
        t = threading.Thread(
            target=self._do_dynamic_load,
            args=(on_complete,),
            daemon=True
        )
        t.start()

    def _do_dynamic_load(self, on_complete):
        try:
            cache_valid = False
            all_tickers = None
            moex_map = None

            if os.path.exists(CACHE_PATH):
                try:
                    mtime = os.path.getmtime(CACHE_PATH)
                    if time.time() - mtime < CACHE_TTL:
                        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                            cache = json.load(f)
                        if cache.get('version') == CACHE_VERSION:
                            all_tickers = cache.get('all_tickers', [])
                            moex_map = cache.get('moex_map', {})
                            cache_valid = True
                except Exception:
                    pass

            if not cache_valid:
                from .sector_index import fetch_all_moex_tickers, fetch_all_sector_tickers_parallel
                all_tickers = fetch_all_moex_tickers()
                moex_map = fetch_all_sector_tickers_parallel()
                try:
                    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
                    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
                        json.dump({'version': CACHE_VERSION, 'all_tickers': all_tickers, 'moex_map': moex_map},
                                  f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

            new_ticker_to_sector = dict(self._ticker_to_sector)
            new_sector_to_tickers = dict(self._sector_to_tickers)

            for ticker in all_tickers:
                if ticker not in new_ticker_to_sector:
                    sector = moex_map.get(ticker, 'Прочее')
                    new_ticker_to_sector[ticker] = sector
                    new_sector_to_tickers.setdefault(sector, []).append(ticker)

            if on_complete:
                import tkinter as tk
                root = tk._default_root
                if root is not None:
                    root.after(0, on_complete, new_ticker_to_sector, new_sector_to_tickers)
                else:
                    on_complete(new_ticker_to_sector, new_sector_to_tickers)
        except Exception:
            logging.warning("Failed to fetch MOEX sector data, using static sectors only")
            if on_complete:
                import tkinter as tk
                root = tk._default_root
                if root is not None:
                    root.after(0, on_complete, None, None)
                else:
                    on_complete(None, None)

    def apply_dynamic_data(self, ticker_to_sector, sector_to_tickers):
        self._ticker_to_sector = ticker_to_sector
        self._sector_to_tickers = sector_to_tickers

    def get_sector(self, ticker):
        return self._ticker_to_sector.get(ticker.upper())

    def get_tickers(self, sectors):
        if not sectors:
            return []
        result = []
        for s in sectors:
            result.extend(self._sector_to_tickers.get(s, []))
        return result

    def get_all_sectors(self):
        return list(self._sector_to_tickers.keys())

    def get_all_tickers(self):
        return list(self._ticker_to_sector.keys())

    def get_ticker_to_sector_map(self):
        return dict(self._ticker_to_sector)
