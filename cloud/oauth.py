import json
import logging
import webbrowser

import requests

from utils import app_dir

_TOKEN_FILE = 'cloud_token.json'
_OAUTH_URL = 'https://oauth.yandex.ru/authorize'
_TOKEN_URL = 'https://oauth.yandex.ru/token'
_VERIFICATION_CODE_REDIRECT = 'https://oauth.yandex.ru/verification_code'

_client_id = None
_client_secret = None


def set_oauth_app(client_id: str, client_secret: str):
    global _client_id, _client_secret
    _client_id = client_id
    _client_secret = client_secret


def get_oauth_app():
    return _client_id, _client_secret


def _token_path():
    return app_dir() + '/' + _TOKEN_FILE


def load_token() -> dict | None:
    try:
        with open(_token_path(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception:
        return None


def save_token(token_data: dict):
    try:
        with open(_token_path(), 'w', encoding='utf-8') as f:
            json.dump(token_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f'cloud_token save error: {e}')


def delete_token():
    try:
        import os
        os.remove(_token_path())
    except Exception:
        pass


def refresh_access_token(refresh_token: str) -> dict | None:
    if not _client_id or not _client_secret:
        return None
    try:
        resp = requests.post(_TOKEN_URL, data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': _client_id,
            'client_secret': _client_secret,
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        save_token(data)
        return data
    except Exception as e:
        logging.error(f'Token refresh error: {e}')
        return None


def get_valid_token() -> str | None:
    token_data = load_token()
    if not token_data:
        return None
    access = token_data.get('access_token')
    if access:
        return access
    refresh = token_data.get('refresh_token')
    if refresh:
        new_data = refresh_access_token(refresh)
        if new_data:
            return new_data.get('access_token')
    return None


def exchange_code_for_token(code: str, redirect_uri: str = None) -> tuple[dict | None, str]:
    if not _client_id or not _client_secret:
        msg = 'OAuth client_id/client_secret не указаны'
        logging.error(msg)
        return None, msg
    if not redirect_uri:
        redirect_uri = _VERIFICATION_CODE_REDIRECT
    try:
        resp = requests.post(_TOKEN_URL, data={
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': _client_id,
            'client_secret': _client_secret,
            'redirect_uri': redirect_uri,
        }, timeout=15)
        data = resp.json()
        if 'error' in data:
            err = data.get('error_description', data['error'])
            logging.error(f'Token exchange error: {err}')
            return None, err
        resp.raise_for_status()
        save_token(data)
        return data, ''
    except requests.exceptions.RequestException as e:
        msg = f'Сетевая ошибка: {e}'
        logging.error(msg)
        return None, msg
    except Exception as e:
        msg = f'Ошибка обмена кода: {e}'
        logging.error(msg)
        return None, msg


def start_oauth_flow() -> tuple[bool, str]:
    if not _client_id:
        msg = 'OAuth client_id не указан'
        logging.error(msg)
        return False, msg

    auth_url = (
        f'{_OAUTH_URL}?response_type=code'
        f'&client_id={_client_id}'
        f'&redirect_uri={_VERIFICATION_CODE_REDIRECT}'
    )
    webbrowser.open(auth_url)
    return False, ''


def manual_code_flow(verification_code: str, redirect_uri: str = None) -> tuple[bool, str]:
    if not _client_id or not _client_secret:
        msg = 'OAuth client_id/client_secret не указаны'
        logging.error(msg)
        return False, msg
    if not verification_code:
        msg = 'Код подтверждения пустой'
        logging.error(msg)
        return False, msg
    token_data, err = exchange_code_for_token(verification_code, redirect_uri=redirect_uri)
    if token_data:
        return True, ''
    return False, err
