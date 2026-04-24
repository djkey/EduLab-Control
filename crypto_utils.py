"""
Утилиты шифрования и подписи команд.

Схема:
  - Сервер генерирует ключ (32 байта) из параметров ПК, кодирует в hex.
  - При спаривании сервер отправляет ключ клиенту по персональному топику.
  - Все команды сервер подписывает HMAC-SHA256.
  - Клиент проверяет подпись перед выполнением команды.
"""

import hashlib
import hmac
import json
import os
import socket
import time
import uuid


def generate_server_key() -> str:
    """Генерирует ключ сервера на основе параметров ПК (32 байта, hex)."""
    raw = f"{socket.gethostname()}-{uuid.getnode()}-SERVER-CLASSROOM"
    return hashlib.sha256(raw.encode()).hexdigest()  # 64 hex символа = 32 байта


def key_to_display(hex_key: str) -> str:
    """Красивое отображение ключа блоками по 4 символа."""
    short = hex_key[:16].upper()
    return "-".join(short[i:i+4] for i in range(0, 16, 4))


def sign_payload(payload: dict, hex_key: str) -> str:
    """
    Сериализует payload в JSON, подписывает HMAC-SHA256.
    Возвращает JSON-строку: {"ts": ..., "data": {...}, "sig": "..."}
    """
    ts = int(time.time())
    body = {"ts": ts, "data": payload}
    body_bytes = json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
    sig = hmac.new(key=bytes.fromhex(hex_key), msg=body_bytes, digestmod=hashlib.sha256).hexdigest()
    body["sig"] = sig
    return json.dumps(body, ensure_ascii=False)


def verify_and_parse(message: str, hex_key: str, max_age_sec: int = 30) -> dict | None:
    """
    Проверяет подпись сообщения. 
    Возвращает payload dict при успехе или None при ошибке/подмене.
    max_age_sec — защита от replay-атак.
    """
    try:
        obj = json.loads(message)
        ts = obj["ts"]
        sig_received = obj["sig"]
        body = {"ts": ts, "data": obj["data"]}
        body_bytes = json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
        sig_expected = hmac.new(
            key=bytes.fromhex(hex_key), msg=body_bytes, digestmod=hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(sig_received, sig_expected):
            return None  # подпись не совпала

        if abs(int(time.time()) - ts) > max_age_sec:
            return None  # старое сообщение (replay)

        return obj["data"]
    except Exception:
        return None
