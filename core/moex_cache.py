import json
import logging
import os
import time
import threading
from typing import Any, Optional

from utils import app_dir

_CACHE_DIR = os.path.join(app_dir(), 'results')
_CACHE_FILE = os.path.join(_CACHE_DIR, 'moex_cache.json')

_TTL_TICKERS = 4 * 3600


class MoexCache:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._mem = {}
                cls._instance._dirty = False
                cls._instance._file_lock = threading.Lock()
                cls._instance._load_disk()
            return cls._instance

    def _load_disk(self):
        if not os.path.exists(_CACHE_FILE):
            return
        try:
            with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
                self._mem = json.load(f)
        except Exception as e:
            logging.debug(f'MoexCache load error: {e}')
            self._mem = {}

    def _save_disk(self):
        if not self._dirty:
            return
        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._mem, f, ensure_ascii=False)
            self._dirty = False
        except Exception as e:
            logging.debug(f'MoexCache save error: {e}')

    def get(self, key: str) -> Optional[Any]:
        entry = self._mem.get(key)
        if entry is None:
            return None
        if time.time() > entry.get('exp', 0):
            del self._mem[key]
            self._dirty = True
            return None
        return entry['val']

    def set(self, key: str, value: Any, ttl: int):
        self._mem[key] = {'val': value, 'exp': time.time() + ttl}
        self._dirty = True

    def flush(self):
        with self._file_lock:
            self._save_disk()

    def cleanup(self):
        now = time.time()
        expired = [k for k, v in self._mem.items() if now > v.get('exp', 0)]
        for k in expired:
            del self._mem[k]
        if expired:
            self._dirty = True


moex_cache = MoexCache()


def cached_get_tickers(fetch_fn):
    key = 'moex_tickers_tqbr'
    result = moex_cache.get(key)
    if result is not None:
        return result
    result = fetch_fn()
    if result:
        moex_cache.set(key, result, _TTL_TICKERS)
        moex_cache.flush()
    return result
