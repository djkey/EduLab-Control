"""
MQTT-обёртка.

Топики:
  classroom/announce          — клиент публикует своё имя и client_id
  classroom/pair/<client_id>  — сервер отправляет ключ конкретному клиенту
  classroom/cmd               — сервер рассылает подписанные команды
  classroom/heartbeat         — клиент регулярно сигнализирует «я онлайн»
"""

import json
import threading

import paho.mqtt.client as mqtt

from config import (
    MQTT_BROKER, MQTT_PORT,
    TOPIC_ANNOUNCE, TOPIC_PAIR_BASE, TOPIC_CMD, TOPIC_HEARTBEAT,
)


class MQTTHandler:
    def __init__(self, client_id: str):
        self._client = mqtt.Client(client_id=client_id, clean_session=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

        # Колбэки, которые устанавливает UI
        self.on_announce = None        # (payload_dict)  — для сервера
        self.on_command = None         # (payload_dict)  — для клиента
        self.on_paired = None          # (hex_key)       — для клиента
        self.on_heartbeat = None       # (payload_dict)  — для сервера
        self.on_connection_change = None  # (bool connected)

        self._role = None  # "server" | "client"
        self._my_client_id = client_id
        self._connected = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    #  Подключение                                                         #
    # ------------------------------------------------------------------ #
    def connect(self):
        self._client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self._client.loop_start()

    def disconnect(self):
        self._client.loop_stop()
        self._client.disconnect()

    # ------------------------------------------------------------------ #
    #  Настройка роли                                                      #
    # ------------------------------------------------------------------ #
    def setup_as_server(self):
        """Сервер слушает анонсы клиентов и heartbeat."""
        self._role = "server"
        if self._connected:
            self._subscribe_server()

    def setup_as_client(self, client_id: str):
        """Клиент слушает свой персональный топик спаривания и команды."""
        self._role = "client"
        self._my_client_id = client_id
        if self._connected:
            self._subscribe_client()

    # ------------------------------------------------------------------ #
    #  Публикация                                                          #
    # ------------------------------------------------------------------ #
    def publish_announce(self, device_name: str, client_id: str):
        """Клиент объявляет себя серверу."""
        payload = json.dumps({"device_name": device_name, "client_id": client_id},
                             ensure_ascii=False)
        self._client.publish(TOPIC_ANNOUNCE, payload, qos=1, retain=False)

    def publish_key_to_client(self, client_id: str, hex_key: str):
        """Сервер отправляет ключ конкретному клиенту."""
        topic = f"{TOPIC_PAIR_BASE}/{client_id}"
        payload = json.dumps({"key": hex_key}, ensure_ascii=False)
        self._client.publish(topic, payload, qos=1, retain=True)

    def publish_command(self, signed_message: str):
        """Сервер публикует подписанную команду всем."""
        self._client.publish(TOPIC_CMD, signed_message, qos=1, retain=False)

    def publish_heartbeat(self, device_name: str, client_id: str):
        """Клиент сигналит «я онлайн»."""
        payload = json.dumps({"device_name": device_name, "client_id": client_id},
                             ensure_ascii=False)
        self._client.publish(TOPIC_HEARTBEAT, payload, qos=0, retain=False)

    # ------------------------------------------------------------------ #
    #  Внутренние обработчики                                              #
    # ------------------------------------------------------------------ #
    def _on_connect(self, client, userdata, flags, rc):
        self._connected = (rc == 0)
        if self.on_connection_change:
            self.on_connection_change(self._connected)
        if self._connected:
            if self._role == "server":
                self._subscribe_server()
            elif self._role == "client":
                self._subscribe_client()

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if self.on_connection_change:
            self.on_connection_change(False)

    def _subscribe_server(self):
        self._client.subscribe(TOPIC_ANNOUNCE, qos=1)
        self._client.subscribe(TOPIC_HEARTBEAT, qos=0)

    def _subscribe_client(self):
        pair_topic = f"{TOPIC_PAIR_BASE}/{self._my_client_id}"
        self._client.subscribe(pair_topic, qos=1)
        self._client.subscribe(TOPIC_CMD, qos=1)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            raw = msg.payload.decode("utf-8")
        except Exception:
            return

        if topic == TOPIC_ANNOUNCE:
            if self.on_announce:
                self.on_announce(json.loads(raw))

        elif topic == TOPIC_HEARTBEAT:
            if self.on_heartbeat:
                self.on_heartbeat(json.loads(raw))

        elif topic.startswith(f"{TOPIC_PAIR_BASE}/"):
            # Клиент получил ключ от сервера
            data = json.loads(raw)
            if self.on_paired and "key" in data:
                self.on_paired(data["key"])

        elif topic == TOPIC_CMD:
            # Клиент получил команду (проверка подписи — в UI-слое)
            if self.on_command:
                self.on_command(raw)
