import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from utils import app_dir

AI_CONFIG_PATH = os.path.join(app_dir(), 'results', 'ai_config.json')

DEFAULT_AI_CONFIG = {
    'provider': 'github_models',
    'api_key': '',
    'model': 'deepseek-large-fast',
    'endpoint': 'https://models.github.ai/inference',
    'auto_scan_interval_min': 15,
    'max_news': 50,
}


GITHUB_MODELS = [
    'deepseek-large-fast',
    'deepseek-chat',
    'gpt-4o',
    'gpt-4o-mini',
    'Meta-Llama-3.1-405B-Instruct',
    'Meta-Llama-3.1-8B-Instruct',
    'Phi-3.5-mini-instruct',
    'Mistral-large',
    'Mixtral-8x7b',
]

GROQ_MODELS = [
    'llama-3.3-70b-versatile',
    'llama-3.1-8b-instant',
    'mixtral-8x7b-32768',
    'gemma-7b-it',
    'gemma2-9b-it',
    'deepseek-r1-distill-llama-70b',
]

OPENROUTER_MODELS = [
    'deepseek/deepseek-chat',
    'openai/gpt-4o',
    'openai/gpt-4o-mini',
    'anthropic/claude-3.5-sonnet',
    'google/gemini-2.0-flash-001',
    'mistralai/mistral-small-24b-instruct',
    'qwen/qwen-2.5-7b-instruct',
    'meta-llama/llama-3.1-8b-instruct',
    'nousresearch/hermes-3-llama-3.1-70b',
    'cohere/command-r-plus',
]

PROVIDER_MODELS = {
    'github_models': GITHUB_MODELS,
    'groq': GROQ_MODELS,
    'openrouter': OPENROUTER_MODELS,
    'rules': [],
}

DEFAULT_MODELS = {
    'github_models': 'deepseek-large-fast',
    'groq': 'llama-3.3-70b-versatile',
    'openrouter': 'deepseek/deepseek-chat',
    'rules': '',
}


def fetch_available_models(provider: str, api_key: str, endpoint: str) -> List[str]:
    if provider == 'rules':
        return []
    try:
        import requests as req
        url = f'{endpoint.rstrip("/")}/v1/models'
        headers = {'Authorization': f'Bearer {api_key}'}
        resp = req.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        api_models = []
        for m in data.get('data', []):
            mid = m.get('id')
            if mid:
                task = m.get('task', '')
                if not task or task in ('chat-completion', 'chat', ''):
                    api_models.append(mid)
        seen = set()
        combined = []
        for m in api_models + PROVIDER_MODELS.get(provider, []):
            if m not in seen:
                seen.add(m)
                combined.append(m)
        return combined if combined else PROVIDER_MODELS.get(provider, [])
    except Exception:
        return list(PROVIDER_MODELS.get(provider, []))


def _read_opencode_openrouter_key() -> str:
    """Try to read OpenRouter API key from opencode auth.json."""
    try:
        auth_path = os.path.join(os.path.expanduser('~'), '.local', 'share', 'opencode', 'auth.json')
        if os.path.exists(auth_path):
            with open(auth_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            key = data.get('openrouter', {}).get('key', '')
            if key:
                return key
    except Exception:
        pass
    return ''


def _read_github_key() -> str:
    """Try to read GitHub Models API key from opencode.json."""
    try:
        cfg_path = os.path.join(os.path.expanduser('~'), '.config', 'opencode', 'opencode.json')
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            key = data.get('provider', {}).get('github', {}).get('apiKey', '')
            if key:
                return key
    except Exception:
        pass
    return ''


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
            raise


class GitHubModelsProvider(AIProvider):
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

    def __init__(self, api_key: str, model: str = 'deepseek-large-fast',
                 endpoint: str = 'https://models.github.ai/inference'):
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint.rstrip('/')

    def analyze(self, title: str, text: str) -> Dict:
        import requests as req
        url = f'{self._endpoint}/v1/chat/completions'
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
            logging.warning(f'GitHub Models API error: {e}')
            raise


class OpenRouterProvider(AIProvider):
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

    def __init__(self, api_key: str, model: str = 'deepseek/deepseek-chat',
                 endpoint: str = 'https://openrouter.ai/api/v1'):
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint.rstrip('/')

    def analyze(self, title: str, text: str) -> Dict:
        import requests as req
        url = f'{self._endpoint}/chat/completions'
        headers = {
            'Authorization': f'Bearer {self._api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/CreateStrategyTrading',
            'X-Title': 'CreateStrategyTrading',
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
            logging.warning(f'OpenRouter API error: {e}')
            raise


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
    provider_name = cfg.get('provider', 'github_models')

    if provider_name == 'github_models':
        api_key = cfg.get('api_key') or _read_github_key()
        if not api_key:
            logging.warning('GitHub Models: API key not found. Using rule-based fallback.')
            return RuleBasedProvider(known_tickers=known_tickers)
        return GitHubModelsProvider(
            api_key=api_key,
            model=cfg.get('model', 'deepseek-large-fast'),
            endpoint=cfg.get('endpoint', 'https://models.github.ai/inference'),
        )

    if provider_name == 'groq':
        api_key = cfg.get('api_key')
        if not api_key:
            logging.warning('Groq: API key not set. Using rule-based fallback.')
            return RuleBasedProvider(known_tickers=known_tickers)
        return GroqProvider(
            api_key=api_key,
            model=cfg.get('model', 'llama-3.3-70b-versatile'),
            endpoint=cfg.get('endpoint', 'https://api.groq.com/openai/v1'),
        )

    if provider_name == 'openrouter':
        api_key = cfg.get('api_key') or _read_opencode_openrouter_key()
        if not api_key:
            logging.warning('OpenRouter: API key not found. Using rule-based fallback.')
            return RuleBasedProvider(known_tickers=known_tickers)
        return OpenRouterProvider(
            api_key=api_key,
            model=cfg.get('model', 'deepseek/deepseek-chat'),
            endpoint=cfg.get('endpoint', 'https://openrouter.ai/api/v1'),
        )

    return RuleBasedProvider(known_tickers=known_tickers)
