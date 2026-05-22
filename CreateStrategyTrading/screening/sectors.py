# sectors.py
import json
import os


SECTORS_PATH = os.path.join(os.path.dirname(__file__), 'sectors.json')


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
