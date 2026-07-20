import json
import logging
import time
import warnings
from typing import Callable

import requests
from urllib3.exceptions import InsecureRequestWarning

from cloud.oauth import get_valid_token

warnings.filterwarnings('ignore', category=InsecureRequestWarning)
_VERIFY_SSL = False

_API_BASE = 'https://cloud-api.yandex.net/v1/disk'
_APP_FOLDER = 'app:/CreateStrategy'


class YandexDiskProvider:
    def __init__(self):
        self._token = None

    def _headers(self):
        if not self._token:
            self._token = get_valid_token()
        if not self._token:
            return None
        return {'Authorization': f'OAuth {self._token}'}

    def _get(self, url: str, params: dict = None) -> dict | None:
        headers = self._headers()
        if not headers:
            return None
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20, verify=_VERIFY_SSL)
            if resp.status_code == 401:
                self._token = None
                headers = self._headers()
                if not headers:
                    return None
                resp = requests.get(url, headers=headers, params=params, timeout=20, verify=_VERIFY_SSL)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.error(f'YandexDisk GET {url}: {e}')
            return None

    def _put(self, url: str, data=None, json_data=None, headers_extra=None) -> bool:
        headers = self._headers()
        if not headers:
            return False
        if headers_extra:
            headers.update(headers_extra)
        try:
            resp = requests.put(url, headers=headers, data=data, json=json_data, timeout=20, verify=_VERIFY_SSL)
            if resp.status_code == 401:
                self._token = None
                headers = self._headers()
                if not headers:
                    return False
                if headers_extra:
                    headers.update(headers_extra)
                resp = requests.put(url, headers=headers, data=data, json=json_data, timeout=20, verify=_VERIFY_SSL)
            return resp.status_code in (200, 201)
        except Exception as e:
            logging.error(f'YandexDisk PUT {url}: {e}')
            return False

    def is_connected(self) -> bool:
        data = self._get(f'{_API_BASE}')
        return data is not None

    def get_user_info(self) -> dict | None:
        return self._get(f'{_API_BASE}')

    def ensure_folder(self) -> tuple[bool, str]:
        headers = self._headers()
        if not headers:
            return False, 'Нет токена'
        try:
            resp = requests.put(f'{_API_BASE}/resources?path={_APP_FOLDER}', headers=headers, timeout=20, verify=_VERIFY_SSL)
            if resp.status_code == 401:
                self._token = None
                headers = self._headers()
                if not headers:
                    return False, 'Нет токена'
                resp = requests.put(f'{_API_BASE}/resources?path={_APP_FOLDER}', headers=headers, timeout=20, verify=_VERIFY_SSL)
            if resp.status_code in (200, 201, 409):
                return True, ''
            msg = f'HTTP {resp.status_code}: {resp.text[:200]}'
            logging.error(f'Ensure folder error: {msg}')
            return False, msg
        except Exception as e:
            msg = f'Ошибка создания папки: {e}'
            logging.error(msg)
            return False, msg

    def list_files(self) -> dict[str, dict] | None:
        data = self._get(f'{_API_BASE}/resources', params={'path': _APP_FOLDER, 'limit': 100})
        if not data:
            return None
        items = data.get('_embedded', data).get('items', [])
        result = {}
        for item in items:
            name = item.get('name', '')
            if item.get('type') == 'file':
                modified = item.get('modified', '')
                result[name] = {
                    'name': name,
                    'modified': modified,
                    'size': item.get('size', 0),
                    'md5': item.get('md5', ''),
                    'path': item.get('path', ''),
                }
        return result

    def upload_file(self, local_path: str, remote_name: str,
                    on_progress: Callable[[int, int], None] = None) -> tuple[bool, str]:
        data = self._get(f'{_API_BASE}/resources/upload',
                         params={'path': f'{_APP_FOLDER}/{remote_name}', 'overwrite': 'true'})
        if not data or 'href' not in data:
            msg = f'Нет URL для загрузки {remote_name}'
            logging.error(msg)
            return False, msg

        upload_url = data['href']
        try:
            with open(local_path, 'rb') as f:
                file_data = f.read()
        except Exception as e:
            msg = f'Ошибка чтения {local_path}: {e}'
            logging.error(msg)
            return False, msg

        try:
            headers = self._headers() or {}
            resp = requests.put(upload_url, data=file_data, headers=headers, timeout=60, verify=_VERIFY_SSL)
            if resp.status_code in (200, 201):
                return True, ''
            msg = f'Загрузка {remote_name}: HTTP {resp.status_code} {resp.reason}'
            logging.error(msg)
            return False, msg
        except Exception as e:
            msg = f'Ошибка загрузки {remote_name}: {e}'
            logging.error(msg)
            return False, msg

    def download_file(self, remote_name: str, local_path: str) -> tuple[bool, str]:
        data = self._get(f'{_API_BASE}/resources/download',
                         params={'path': f'{_APP_FOLDER}/{remote_name}'})
        if not data or 'href' not in data:
            msg = f'Нет URL для скачивания {remote_name}'
            logging.error(msg)
            return False, msg

        download_url = data['href']
        try:
            resp = requests.get(download_url, timeout=60, verify=_VERIFY_SSL)
            resp.raise_for_status()
            import os
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(resp.content)
            return True, ''
        except Exception as e:
            msg = f'Ошибка скачивания {remote_name}: {e}'
            logging.error(msg)
            return False, msg

    def delete_file(self, remote_name: str) -> bool:
        headers = self._headers()
        if not headers:
            return False
        try:
            resp = requests.delete(
                f'{_API_BASE}/resources',
                headers=headers,
                params={'path': f'{_APP_FOLDER}/{remote_name}', 'permanently': 'true'},
                timeout=20, verify=_VERIFY_SSL)
            return resp.status_code in (200, 202, 204)
        except Exception as e:
            logging.error(f'Delete error {remote_name}: {e}')
            return False

    def get_file_metadata(self, remote_name: str) -> dict | None:
        data = self._get(f'{_API_BASE}/resources',
                         params={'path': f'{_APP_FOLDER}/{remote_name}'})
        if not data:
            return None
        return {
            'name': data.get('name', ''),
            'modified': data.get('modified', ''),
            'size': data.get('size', 0),
            'md5': data.get('md5', ''),
        }


provider = YandexDiskProvider()
