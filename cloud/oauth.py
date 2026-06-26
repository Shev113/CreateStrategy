import json
import logging
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

from utils import app_dir

_TOKEN_FILE = 'cloud_token.json'
_OAUTH_URL = 'https://oauth.yandex.ru/authorize'
_TOKEN_URL = 'https://oauth.yandex.ru/token'
_DEFAULT_REDIRECT_PORT = 9876
_DEFAULT_REDIRECT_URI = f'http://localhost:{_DEFAULT_REDIRECT_PORT}'

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


class _OAuthHandler(BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        code = params.get('code', [None])[0]
        error = params.get('error', [None])[0]

        if code:
            _OAuthHandler.auth_code = code
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(
                '<html><body style="background:#1e1e1e;color:#fff;font-family:sans-serif;'
                'display:flex;align-items:center;justify-content:center;height:100vh">'
                '<h2>&#10004; Авторизация успешна! Можно закрыть это окно.</h2></body></html>'.encode('utf-8'))
        elif error:
            _OAuthHandler.auth_code = None
            self.send_response(400)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            err_desc = params.get('error_description', ['Ошибка авторизации'])[0]
            self.wfile.write(
                f'<html><body style="background:#1e1e1e;color:#f66;font-family:sans-serif;'
                f'display:flex;align-items:center;justify-content:center;height:100vh">'
                f'<h2>&#10008; {err_desc}</h2></body></html>'.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def exchange_code_for_token(code: str) -> dict | None:
    if not _client_id or not _client_secret:
        logging.error('OAuth client_id/client_secret not set')
        return None
    try:
        resp = requests.post(_TOKEN_URL, data={
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': _client_id,
            'client_secret': _client_secret,
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        save_token(data)
        return data
    except Exception as e:
        logging.error(f'Token exchange error: {e}')
        return None


def start_oauth_flow(callback=None) -> bool:
    if not _client_id:
        logging.error('OAuth client_id not set')
        return False

    _OAuthHandler.auth_code = None
    redirect_uri = _DEFAULT_REDIRECT_URI
    auth_url = (
        f'{_OAUTH_URL}?response_type=code'
        f'&client_id={_client_id}'
        f'&redirect_uri={redirect_uri}'
    )

    server = None
    try:
        server = HTTPServer(('127.0.0.1', _DEFAULT_REDIRECT_PORT), _OAuthHandler)
        server.timeout = 120
    except OSError:
        webbrowser.open(auth_url)
        return False

    webbrowser.open(auth_url)

    server.handle_request()
    server.server_close()

    code = _OAuthHandler.auth_code
    if not code:
        return False

    token_data = exchange_code_for_token(code)
    if token_data and callback:
        callback(token_data)

    return token_data is not None
