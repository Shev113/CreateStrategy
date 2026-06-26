import logging
from datetime import datetime
from typing import Dict, List, Optional

from news.fetcher import fetch_news_list, fetch_news_body, NewsCache
from news.provider import create_provider, load_ai_config, AIProvider


class NewsAnalyzer:
    def __init__(self, known_tickers: List[str] = None):
        self._known_tickers = known_tickers or []
        self._cache = NewsCache()
        self._provider: Optional[AIProvider] = None
        self._rebuild_provider()

    def _rebuild_provider(self):
        self._provider = create_provider(known_tickers=self._known_tickers)

    def set_known_tickers(self, tickers: List[str]):
        self._known_tickers = tickers
        self._rebuild_provider()

    def fetch_and_analyze(self, count: int = 50) -> List[Dict]:
        news_list = fetch_news_list(count=count)
        if not news_list:
            return []

        results = []
        for item in news_list:
            news_id = item.get('id')
            if not news_id:
                continue

            cached = self._cache.get_analysis(news_id)
            if cached:
                results.append(cached)
                continue

            body = fetch_news_body(news_id) or ''
            analysis = self._provider.analyze(item.get('title', ''), body)
            analysis['id'] = news_id
            analysis['title'] = item.get('title', '')
            analysis['published_at'] = item.get('published_at', '')
            analysis['analyzed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
            self._cache.save_analysis(news_id, analysis)
            results.append(analysis)

        results.sort(key=lambda x: x.get('published_at', ''), reverse=True)
        return results

    def get_cached(self) -> List[Dict]:
        return self._cache.get_all_analyzed()

    def analyze_single(self, news_id: int, title: str, body: str = '') -> Dict:
        cached = self._cache.get_analysis(news_id)
        if cached:
            return cached

        if not body:
            body = fetch_news_body(news_id) or ''

        analysis = self._provider.analyze(title, body)
        analysis['id'] = news_id
        analysis['title'] = title
        analysis['analyzed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        self._cache.save_analysis(news_id, analysis)
        return analysis
