import json
import logging
import os
import html
import time
from datetime import datetime
from typing import List, Dict, Optional

from utils import app_dir
from core.moex_session import MOEX_SESSION

NEWS_CACHE_PATH = os.path.join(app_dir(), 'results', 'news_cache.json')
MOEX_NEWS_URL = 'https://iss.moex.com/iss/sitenews.json'
MOEX_NEWS_ITEM_URL = 'https://iss.moex.com/iss/sitenews/{id}.json'


def fetch_news_list(count: int = 50, start: int = 0) -> List[Dict]:
    try:
        url = f'{MOEX_NEWS_URL}?start={start}&count={count}'
        resp = MOEX_SESSION.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        columns = data.get('sitenews', {}).get('columns', [])
        rows = data.get('sitenews', {}).get('data', [])
        news_list = []
        for row in rows:
            item = dict(zip(columns, row))
            news_list.append({
                'id': item.get('id'),
                'title': html.unescape(item.get('title', '')),
                'published_at': str(item.get('published_at', '')),
                'modified_at': str(item.get('modified_at', '')),
            })
        return news_list
    except Exception as e:
        logging.warning(f'News fetch error: {e}')
        return []


def fetch_news_body(news_id: int) -> Optional[str]:
    try:
        url = MOEX_NEWS_ITEM_URL.format(id=news_id)
        resp = MOEX_SESSION.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        columns = data.get('content', {}).get('columns', [])
        rows = data.get('content', {}).get('data', [])
        if rows:
            item = dict(zip(columns, rows[0]))
            return html.unescape(item.get('body', ''))
    except Exception as e:
        logging.warning(f'News body fetch error for {news_id}: {e}')
    return None


class NewsCache:
    def __init__(self, path=None):
        self._path = path or NEWS_CACHE_PATH
        self._cache: Dict = {}
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=1)
        except Exception as e:
            logging.warning(f'News cache save error: {e}')

    def get_analysis(self, news_id: int) -> Optional[Dict]:
        return self._cache.get(str(news_id))

    def save_analysis(self, news_id: int, analysis: Dict):
        self._cache[str(news_id)] = analysis
        if len(self._cache) > 1000:
            oldest = sorted(self._cache.items(),
                           key=lambda x: x[1].get('analyzed_at', ''))[:200]
            for k, _ in oldest:
                del self._cache[k]
        self._save()

    def get_all_analyzed(self) -> List[Dict]:
        return list(self._cache.values())
