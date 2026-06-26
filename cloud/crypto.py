import hashlib
import hmac
import json
import os
import base64
import struct

_SALT_PREFIX = b'CreateStrategySync'
_ITERATIONS = 100000
_KEY_LEN = 32


def _derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, _ITERATIONS, dklen=_KEY_LEN)


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def encrypt_json(data: dict, password: str) -> str:
    salt = os.urandom(16)
    key = _derive_key(password, _SALT_PREFIX + salt)
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    encrypted = _xor_bytes(payload, key)
    mac = hmac.new(key, encrypted, hashlib.sha256).digest()
    packed = struct.pack('>B', len(salt)) + salt + mac + encrypted
    return base64.b64encode(packed).decode('ascii')


def decrypt_json(token: str, password: str) -> dict | None:
    try:
        raw = base64.b64decode(token)
        salt_len = raw[0]
        salt = raw[1:1 + salt_len]
        mac = raw[1 + salt_len:1 + salt_len + 32]
        encrypted = raw[1 + salt_len + 32:]
        key = _derive_key(password, _SALT_PREFIX + salt)
        if not hmac.compare_digest(mac, hmac.new(key, encrypted, hashlib.sha256).digest()):
            return None
        payload = _xor_bytes(encrypted, key)
        return json.loads(payload.decode('utf-8'))
    except Exception:
        return None


def obfuscate_json(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return base64.b64encode(payload).decode('ascii')


def deobfuscate_json(token: str) -> dict | None:
    try:
        payload = base64.b64decode(token)
        return json.loads(payload.decode('utf-8'))
    except Exception:
        return None
