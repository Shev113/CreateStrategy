import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from utils import app_dir

AI_CONFIG_PATH = os.path.join(app_dir(), 'results', 'ai_config.json')

DEFAULT_AI_CONFIG = {
    'provider': 'rules',
    'api_key': '',
    'model': 'llama-3.3-70b-versatile',
    'endpoint': 'https://api.groq.com/openai/v1',
    'auto_scan_interval_min': 15,
    'max_news': 50,
}


class AIProvider(ABC):
    @abstractmethod
    def analyze(self, title: str, text: str) -> Dict:
        pass


class RuleBasedProvider(AIProvider):
    POSITIVE_WORDS = [
        'рост', 'прибыл', 'увеличен', 'повышен', 'рекорд', 'превыш',
        'положительн', 'стабильн', 'включен', 'допущен', 'улучшен',
        'расшир', 'приобрет', 'выкуп', 'дивиденд', 'купон', 'размещен',
        'зарегистрирован', 'одобрен', 'принят', 'создан', 'запущен',
    ]
    NEGATIVE_WORDS = [
        'снижен', 'падени', 'убытк', 'исключен', 'прекращ', 'ограничен',
        'дестабилиз', 'риск', 'блокир', 'приостан', 'отменён', 'отменен',
        'дефолт', 'дефолтн', 'просроч', 'невыполн', 'нарушен',
        'уменьшен', 'сокращ', 'снижени', 'убыток', 'убытк',
    ]
    TICKER_PATTERN = r'\b([A-Z]{2,5})\b'

    def __init__(self, known_tickers=None):
        self._known_tickers = set(known_tickers) if known_tickers else set()

    def analyze(self, title: str, text: str) -> Dict:
        combined = f'{title} {text}'.lower()
        pos_count = sum(1 for w in self.POSITIVE_WORDS if w in combined)
        neg_count = sum(1 for w in self.NEGATIVE_WORDS if w in combined)

        if pos_count > neg_count:
            sentiment = 'positive'
            score = min(pos_count / max(pos_count + neg_count, 1), 1.0)
        elif neg_count > pos_count:
            sentiment = 'negative'
            score = -min(neg_count / max(pos_count + neg_count, 1), 1.0)
        else:
            sentiment = 'neutral'
            score = 0.0

        tickers = self._extract_tickers(title, text)
        impact = min(pos_count + neg_count, 5)
        if impact > 0 and sentiment == 'neutral':
            impact = max(1, impact - 1)

        if impact >= 3:
            recommendation = 'действовать'
        elif impact >= 1:
            recommendation = 'наблюдать'
        else:
            recommendation = 'игнорировать'

        return {
            'sentiment': sentiment,
            'score': round(score, 2),
            'impact': impact,
            'tickers': tickers,
            'summary': title[:200],
            'recommendation': recommendation,
        }

    def _extract_tickers(self, title: str, text: str) -> List[str]:
        import re
        combined = f'{title} {text}'
        candidates = re.findall(self.TICKER_PATTERN, combined)
        blacklist = {'ПО', 'АО', 'ООО', 'РФ', 'ЦК', 'НКЦ', 'КБ', 'НКО', 'УФК',
                     'СНГ', 'МО', 'СШ', 'ЗА', 'НА', 'ИЗ', 'ДО', 'ПЯ', 'ФИ'}
        tickers = []
        for c in candidates:
            if c in blacklist:
                continue
            if self._known_tickers and c in self._known_tickers:
                tickers.append(c)
            elif not self._known_tickers and len(c) >= 2 and c not in blacklist:
                tickers.append(c)
        return list(dict.fromkeys(tickers))[:10]


class GroqProvider(AIProvider):
    SYSTEM_PROMPT = """Ты — аналитик российского фондового рынка. Проанализируй финансовую новость.
Ответь ТОЛЬКО в формате JSON (без markdown, без ```):
{
  "sentiment": "positive" | "neutral" | "negative",
  "score": -1.0 .. 1.0,
  "impact": 1..5,
  "tickers": ["TICKER1", "TICKER2"],
  "summary": "Краткое резюме 1-2 предложения",
  "recommendation": "наблюдать" | "действовать" | "игнорировать"
}"""

    def __init__(self, api_key: str, model: str = 'llama-3.3-70b-versatile',
                 endpoint: str = 'https://api.groq.com/openai/v1'):
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint.rstrip('/')

    def analyze(self, title: str, text: str) -> Dict:
        import requests as req
        url = f'{self._endpoint}/chat/completions'
        headers = {
            'Authorization': f'Bearer {self._api_key}',
            'Content-Type': 'application/json',
        }
        user_msg = f'Заголовок: {title}\n\nТекст: {text[:2000]}'
        payload = {
            'model': self._model,
            'messages': [
                {'role': 'system', 'content': self.SYSTEM_PROMPT},
                {'role': 'user', 'content': user_msg},
            ],
            'temperature': 0.1,
            'max_tokens': 500,
        }
        try:
            resp = req.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            content = data['choices'][0]['message']['content'].strip()
            content = content.strip('`').strip()
            if content.startswith('json'):
                content = content[4:].strip()
            result = json.loads(content)
            for key in ('sentiment', 'score', 'impact', 'tickers', 'summary', 'recommendation'):
                result.setdefault(key, '' if key in ('summary', 'recommendation') else
                                       [] if key == 'tickers' else 0)
            return result
        except Exception as e:
            logging.warning(f'Groq API error: {e}')
            fallback = RuleBasedProvider()
            return fallback.analyze(title, text)


def load_ai_config() -> Dict:
    if os.path.exists(AI_CONFIG_PATH):
        try:
            with open(AI_CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            merged = dict(DEFAULT_AI_CONFIG)
            merged.update(cfg)
            return merged
        except Exception:
            pass
    return dict(DEFAULT_AI_CONFIG)


def save_ai_config(cfg: Dict):
    try:
        os.makedirs(os.path.dirname(AI_CONFIG_PATH), exist_ok=True)
        with open(AI_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f'AI config save error: {e}')


def create_provider(config: Dict = None, known_tickers=None) -> AIProvider:
    cfg = config or load_ai_config()
    provider_name = cfg.get('provider', 'rules')
    if provider_name == 'groq' and cfg.get('api_key'):
        return GroqProvider(
            api_key=cfg['api_key'],
            model=cfg.get('model', 'llama-3.3-70b-versatile'),
            endpoint=cfg.get('endpoint', 'https://api.groq.com/openai/v1'),
        )
    return RuleBasedProvider(known_tickers=known_tickers)
