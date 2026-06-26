import json
import logging
import os
import time
from typing import Callable

from cloud.crypto import encrypt_json, decrypt_json, obfuscate_json, deobfuscate_json
from cloud.oauth import get_valid_token, load_token, delete_token, save_token, set_oauth_app
from cloud.provider import provider, YandexDiskProvider

_SYNC_FILES = [
    'favorites.json',
    'ticker_settings.json',
    'session_state.json',
    'notifications.json',
    'automation.json',
    'ai_config.json',
    'signals.json',
    'diary.json',
    'price_alerts.json',
    'watchlist.json',
    'news_cache.json',
]

_ENCRYPTED_FILES = {'ai_config.json'}
_CLOUD_META_FILE = '_cloud_meta.json'


def get_sync_files():
    return list(_SYNC_FILES)


def is_encrypted_file(name: str) -> bool:
    return name in _ENCRYPTED_FILES


def _results_dir() -> str:
    from utils import app_dir
    return os.path.join(app_dir(), 'results')


def _local_path(name: str) -> str:
    return os.path.join(_results_dir(), name)


def _local_mtime(name: str) -> float:
    path = _local_path(name)
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def _read_local(name: str) -> dict | None:
    path = _local_path(name)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _write_local(name: str, data: dict):
    path = _local_path(name)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f'Write local error {name}: {e}')


def _load_cloud_meta() -> dict:
    from utils import app_dir
    meta_path = os.path.join(app_dir(), 'results', _CLOUD_META_FILE)
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cloud_meta(meta: dict):
    from utils import app_dir
    meta_path = os.path.join(app_dir(), 'results', _CLOUD_META_FILE)
    try:
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f'Save cloud meta error: {e}')


class SyncResult:
    def __init__(self):
        self.uploaded = []
        self.downloaded = []
        self.skipped = []
        self.conflicts = []
        self.errors = []

    def summary(self) -> str:
        parts = []
        if self.uploaded:
            parts.append(f'Загружено: {len(self.uploaded)}')
        if self.downloaded:
            parts.append(f'Скачано: {len(self.downloaded)}')
        if self.skipped:
            parts.append(f'Без изменений: {len(self.skipped)}')
        if self.conflicts:
            parts.append(f'Конфликты: {len(self.conflicts)}')
        if self.errors:
            parts.append(f'Ошибки: {len(self.errors)}')
        return ' | '.join(parts) if parts else 'Нет изменений'


class SyncManager:
    def __init__(self):
        self._sync_password = ''
        self._auto_sync_on_close = False
        self._client_id = ''
        self._client_secret = ''
        self._load_config()

    def _config_path(self) -> str:
        from utils import app_dir
        return os.path.join(app_dir(), 'results', 'cloud_config.json')

    def _load_config(self):
        try:
            with open(self._config_path(), 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            self._sync_password = cfg.get('sync_password', '')
            self._auto_sync_on_close = cfg.get('auto_sync_on_close', False)
            self._client_id = cfg.get('client_id', '')
            self._client_secret = cfg.get('client_secret', '')
            if self._client_id and self._client_secret:
                set_oauth_app(self._client_id, self._client_secret)
        except Exception:
            pass

    def save_config(self):
        try:
            with open(self._config_path(), 'w', encoding='utf-8') as f:
                json.dump({
                    'sync_password': self._sync_password,
                    'auto_sync_on_close': self._auto_sync_on_close,
                    'client_id': self._client_id,
                    'client_secret': self._client_secret,
                }, f, ensure_ascii=False, indent=2)
            if self._client_id and self._client_secret:
                set_oauth_app(self._client_id, self._client_secret)
        except Exception as e:
            logging.error(f'Save cloud config error: {e}')

    @property
    def sync_password(self) -> str:
        return self._sync_password

    @sync_password.setter
    def sync_password(self, value: str):
        self._sync_password = value

    @property
    def auto_sync_on_close(self) -> bool:
        return self._auto_sync_on_close

    @auto_sync_on_close.setter
    def auto_sync_on_close(self, value: bool):
        self._auto_sync_on_close = value

    @property
    def client_id(self) -> str:
        return self._client_id

    @client_id.setter
    def client_id(self, value: str):
        self._client_id = value

    @property
    def client_secret(self) -> str:
        return self._client_secret

    @client_secret.setter
    def client_secret(self, value: str):
        self._client_secret = value

    def is_connected(self) -> bool:
        return get_valid_token() is not None

    def disconnect(self):
        delete_token()
        self._sync_password = ''
        self.save_config()

    def _prepare_upload_data(self, name: str, data: dict) -> tuple[str, dict]:
        if is_encrypted_file(name) and self._sync_password:
            encrypted = encrypt_json(data, self._sync_password)
            return name + '.enc', {'encrypted': True, 'data': encrypted}
        elif is_encrypted_file(name):
            return name + '.b64', {'obfuscated': True, 'data': obfuscate_json(data)}
        return name, data

    def _prepare_download_data(self, name: str, remote_data: dict) -> dict | None:
        if not isinstance(remote_data, dict):
            return remote_data
        if remote_data.get('encrypted'):
            if not self._sync_password:
                logging.warning(f'{name} encrypted but no password')
                return None
            return decrypt_json(remote_data['data'], self._sync_password)
        if remote_data.get('obfuscated'):
            return deobfuscate_json(remote_data['data'])
        return remote_data

    def _remote_name(self, name: str) -> str:
        if is_encrypted_file(name) and self._sync_password:
            return name + '.enc'
        elif is_encrypted_file(name):
            return name + '.b64'
        return name

    def upload_all(self, on_progress: Callable[[str, int, int], None] = None) -> SyncResult:
        result = SyncResult()
        if not self.is_connected():
            result.errors.append('Не подключено к Яндекс.Диску')
            return result

        if not provider.ensure_folder():
            result.errors.append('Не удалось создать папку на Яндекс.Диске')
            return result

        meta = _load_cloud_meta()
        total = len(_SYNC_FILES)

        for i, name in enumerate(_SYNC_FILES):
            if on_progress:
                on_progress(name, i + 1, total)

            local_data = _read_local(name)
            if local_data is None:
                result.skipped.append(name)
                continue

            remote_name, upload_data = self._prepare_upload_data(name, local_data)
            local_mtime = _local_mtime(name)

            tmp_path = _local_path('_cloud_upload_tmp.json')
            try:
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(upload_data, f, ensure_ascii=False, indent=2)

                if provider.upload_file(tmp_path, remote_name):
                    meta[name] = {
                        'last_sync': time.time(),
                        'local_mtime': local_mtime,
                        'remote_name': remote_name,
                    }
                    result.uploaded.append(name)
                else:
                    result.errors.append(name)
            except Exception as e:
                logging.error(f'Upload error {name}: {e}')
                result.errors.append(name)
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        _save_cloud_meta(meta)
        return result

    def download_all(self, on_progress: Callable[[str, int, int], None] = None) -> SyncResult:
        result = SyncResult()
        if not self.is_connected():
            result.errors.append('Не подключено к Яндекс.Диску')
            return result

        remote_files = provider.list_files()
        if remote_files is None:
            result.errors.append('Не удалось получить список файлов')
            return result

        meta = _load_cloud_meta()
        total = len(_SYNC_FILES)

        for i, name in enumerate(_SYNC_FILES):
            if on_progress:
                on_progress(name, i + 1, total)

            remote_name = self._remote_name(name)
            if remote_name not in remote_files:
                for alt_ext in ['.enc', '.b64', '']:
                    alt_name = name + alt_ext if alt_ext else name
                    if alt_name in remote_files:
                        remote_name = alt_name
                        break
                else:
                    result.skipped.append(name)
                    continue

            tmp_path = _local_path('_cloud_download_tmp.json')
            try:
                if not provider.download_file(remote_name, tmp_path):
                    result.errors.append(name)
                    continue

                with open(tmp_path, 'r', encoding='utf-8') as f:
                    remote_data = json.load(f)

                final_data = self._prepare_download_data(name, remote_data)
                if final_data is not None:
                    _write_local(name, final_data)
                    meta[name] = {
                        'last_sync': time.time(),
                        'local_mtime': _local_mtime(name),
                        'remote_name': remote_name,
                    }
                    result.downloaded.append(name)
                else:
                    result.errors.append(f'{name} (дешифровка)')
            except Exception as e:
                logging.error(f'Download error {name}: {e}')
                result.errors.append(name)
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        _save_cloud_meta(meta)
        return result

    def sync_bidirectional(self, on_progress: Callable[[str, int, int], None] = None) -> SyncResult:
        result = SyncResult()
        if not self.is_connected():
            result.errors.append('Не подключено к Яндекс.Диску')
            return result

        if not provider.ensure_folder():
            result.errors.append('Не удалось создать папку на Яндекс.Диске')
            return result

        remote_files = provider.list_files()
        if remote_files is None:
            result.errors.append('Не удалось получить список файлов')
            return result

        meta = _load_cloud_meta()
        total = len(_SYNC_FILES)

        for i, name in enumerate(_SYNC_FILES):
            if on_progress:
                on_progress(name, i + 1, total)

            local_data = _read_local(name)
            local_mtime = _local_mtime(name)
            remote_name = self._remote_name(name)

            found_remote = remote_name in remote_files
            if not found_remote:
                for alt_ext in ['.enc', '.b64', '']:
                    alt_name = name + alt_ext if alt_ext else name
                    if alt_name in remote_files:
                        remote_name = alt_name
                        found_remote = True
                        break

            has_local = local_data is not None

            if not has_local and not found_remote:
                result.skipped.append(name)
                continue

            if has_local and not found_remote:
                remote_name_up, upload_data = self._prepare_upload_data(name, local_data)
                tmp_path = _local_path('_cloud_upload_tmp.json')
                try:
                    with open(tmp_path, 'w', encoding='utf-8') as f:
                        json.dump(upload_data, f, ensure_ascii=False, indent=2)
                    if provider.upload_file(tmp_path, remote_name_up):
                        meta[name] = {'last_sync': time.time(), 'local_mtime': local_mtime, 'remote_name': remote_name_up}
                        result.uploaded.append(name)
                    else:
                        result.errors.append(name)
                except Exception as e:
                    result.errors.append(name)
                finally:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                continue

            if not has_local and found_remote:
                tmp_path = _local_path('_cloud_download_tmp.json')
                try:
                    if provider.download_file(remote_name, tmp_path):
                        with open(tmp_path, 'r', encoding='utf-8') as f:
                            remote_data = json.load(f)
                        final_data = self._prepare_download_data(name, remote_data)
                        if final_data is not None:
                            _write_local(name, final_data)
                            meta[name] = {'last_sync': time.time(), 'local_mtime': _local_mtime(name), 'remote_name': remote_name}
                            result.downloaded.append(name)
                        else:
                            result.errors.append(f'{name} (дешифровка)')
                    else:
                        result.errors.append(name)
                except Exception as e:
                    result.errors.append(name)
                finally:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                continue

            prev_sync = meta.get(name, {})
            last_sync_time = prev_sync.get('last_sync', 0)
            prev_local_mtime = prev_sync.get('local_mtime', 0)

            local_changed = local_mtime > last_sync_time
            remote_info = remote_files.get(remote_name, {})
            remote_modified = remote_info.get('modified', '')
            remote_changed = True

            if remote_modified:
                try:
                    from datetime import datetime
                    rt = datetime.fromisoformat(remote_modified.replace('Z', '+00:00'))
                    remote_ts = rt.timestamp()
                    remote_changed = remote_ts > last_sync_time
                except Exception:
                    pass

            if local_changed and not remote_changed:
                remote_name_up, upload_data = self._prepare_upload_data(name, local_data)
                tmp_path = _local_path('_cloud_upload_tmp.json')
                try:
                    with open(tmp_path, 'w', encoding='utf-8') as f:
                        json.dump(upload_data, f, ensure_ascii=False, indent=2)
                    if provider.upload_file(tmp_path, remote_name_up):
                        meta[name] = {'last_sync': time.time(), 'local_mtime': local_mtime, 'remote_name': remote_name_up}
                        result.uploaded.append(name)
                    else:
                        result.errors.append(name)
                except Exception:
                    result.errors.append(name)
                finally:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
            elif remote_changed and not local_changed:
                tmp_path = _local_path('_cloud_download_tmp.json')
                try:
                    if provider.download_file(remote_name, tmp_path):
                        with open(tmp_path, 'r', encoding='utf-8') as f:
                            remote_data = json.load(f)
                        final_data = self._prepare_download_data(name, remote_data)
                        if final_data is not None:
                            _write_local(name, final_data)
                            meta[name] = {'last_sync': time.time(), 'local_mtime': _local_mtime(name), 'remote_name': remote_name}
                            result.downloaded.append(name)
                        else:
                            result.errors.append(f'{name} (дешифровка)')
                    else:
                        result.errors.append(name)
                except Exception:
                    result.errors.append(name)
                finally:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
            elif local_changed and remote_changed:
                result.conflicts.append(name)
            else:
                result.skipped.append(name)

        _save_cloud_meta(meta)
        return result


sync_manager = SyncManager()
