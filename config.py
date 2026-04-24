"""
Конфигурация приложения.

Структура config.json:
  Для сервера:
    {"role": "server", "key": "<hex>", "display_key": "XXXX-XXXX-XXXX-XXXX"}

  Для клиента (до спаривания):
    {"role": "client", "device_name": "ПК-1", "client_id": "<uuid>"}

  Для клиента (после спаривания):
    {"role": "client", "device_name": "ПК-1", "client_id": "<uuid>", "key": "<hex>"}
"""

import json
import os
import uuid

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

# MQTT брокер (публичный, без регистрации)
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

# Топики
TOPIC_ANNOUNCE   = "classroom/announce"        # клиент → сервер: «я есть»
TOPIC_PAIR_BASE  = "classroom/pair"            # сервер → клиент: «вот ключ»  /pair/<client_id>
TOPIC_CMD        = "classroom/cmd"             # сервер → все: команды
TOPIC_HEARTBEAT  = "classroom/heartbeat"       # клиент → сервер: «я онлайн»


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(data: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_first_run() -> bool:
    return not os.path.exists(CONFIG_FILE)


def new_client_id() -> str:
    return str(uuid.uuid4())
