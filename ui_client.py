"""
Окно клиента:
  1. Ввод имени устройства (если ещё не сохранено)
  2. Ожидание спаривания с сервером
  3. После спаривания — иконка в трее, окно скрывается
"""

import socket
import threading

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QDialog, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QSystemTrayIcon, QMenu, QAction,
    QApplication,
)

from config import load_config, save_config, new_client_id
from mqtt_handler import MQTTHandler
from crypto_utils import verify_and_parse

import webbrowser


class _Signals(QObject):
    paired = pyqtSignal()
    command = pyqtSignal(str)          # raw signed json
    connection_changed = pyqtSignal(bool)


class ClientWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Дистанционное управление — Ученик")
        self.setFixedSize(420, 300)
        self.setStyleSheet("background:#1e1e2e; color:#cdd6f4;")

        self._cfg = load_config()
        self._signals = _Signals()
        self._signals.paired.connect(self._on_paired)
        self._signals.command.connect(self._on_command)
        self._signals.connection_changed.connect(self._on_connection)

        self._mqtt: MQTTHandler | None = None
        self._heartbeat_timer = QTimer()
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)

        self._build()

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(16)

        self.status_label = QLabel("⏳ Подключение к серверу...")
        self.status_label.setFont(QFont("Segoe UI", 13))
        self.status_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.status_label)

        # --- Поле имени (показываем только при первом запуске) --- #
        has_name = bool(self._cfg.get("device_name"))
        self.name_widget_container = QVBoxLayout()

        self.name_label = QLabel("Введите имя этого компьютера:")
        self.name_label.setStyleSheet("color:#a6adc8; font-size:12px;")
        self.name_label.setAlignment(Qt.AlignCenter)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Например: ПК-Вася")
        self.name_input.setText(self._cfg.get("device_name", socket.gethostname()))
        self.name_input.setStyleSheet("""
            QLineEdit {
                background:#313244; border:1px solid #585b70;
                border-radius:8px; padding:6px 12px;
                color:#cdd6f4; font-size:13px;
            }
            QLineEdit:focus { border-color:#89b4fa; }
        """)

        self.name_widget_container.addWidget(self.name_label)
        self.name_widget_container.addWidget(self.name_input)
        root.addLayout(self.name_widget_container)

        if has_name:
            self.name_label.hide()
            self.name_input.hide()

        # --- Кнопка --- #
        self.connect_btn = QPushButton("Подключиться")
        self.connect_btn.setFixedHeight(44)
        self.connect_btn.setCursor(Qt.PointingHandCursor)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background:#89b4fa; color:#1e1e2e;
                border-radius:10px; font-size:13px; font-weight:bold;
            }
            QPushButton:hover { background:#b4d0f7; }
            QPushButton:disabled { background:#45475a; color:#585b70; }
        """)
        self.connect_btn.clicked.connect(self._start_connect)
        root.addWidget(self.connect_btn)

        self.pair_status = QLabel("")
        self.pair_status.setAlignment(Qt.AlignCenter)
        self.pair_status.setStyleSheet("color:#a6adc8; font-size:11px;")
        root.addWidget(self.pair_status)

        # Если уже спарен — сразу стартуем
        if self._cfg.get("key") and self._cfg.get("client_id"):
            self.connect_btn.setText("Переподключиться")
            self.pair_status.setText("✅ Устройство зарегистрировано")
            self._start_connect()

    # ------------------------------------------------------------------ #
    #  MQTT                                                                #
    # ------------------------------------------------------------------ #
    def _start_connect(self):
        name = self.name_input.text().strip() or socket.gethostname()
        self._cfg["device_name"] = name
        if not self._cfg.get("client_id"):
            self._cfg["client_id"] = new_client_id()
        save_config(self._cfg)

        self.connect_btn.setEnabled(False)
        self.name_input.setEnabled(False)
        self.status_label.setText("⏳ Подключение к облаку...")

        self._mqtt = MQTTHandler(self._cfg["client_id"])
        self._mqtt.on_connection_change = lambda ok: self._signals.connection_changed.emit(ok)
        self._mqtt.on_paired = lambda key: self._on_paired_raw(key)
        self._mqtt.on_command = lambda raw: self._signals.command.emit(raw)
        self._mqtt.setup_as_client(self._cfg["client_id"])
        self._mqtt.connect()

    def _on_paired_raw(self, hex_key: str):
        """Вызывается из MQTT-потока."""
        self._cfg["key"] = hex_key
        save_config(self._cfg)
        self._signals.paired.emit()

    def _send_heartbeat(self):
        if self._mqtt:
            self._mqtt.publish_heartbeat(
                self._cfg.get("device_name", "?"),
                self._cfg["client_id"],
            )

    # ------------------------------------------------------------------ #
    #  Сигналы (выполняются в UI-потоке)                                  #
    # ------------------------------------------------------------------ #
    def _on_connection(self, ok: bool):
        if ok:
            self.status_label.setText("🌐 Подключено. Ожидание учителя...")
            # Анонсируем себя серверу
            self._mqtt.publish_announce(
                self._cfg["device_name"], self._cfg["client_id"]
            )
            # Если уже спарены — запускаем heartbeat
            if self._cfg.get("key"):
                self._heartbeat_timer.start(15_000)
        else:
            self.status_label.setText("⚠️ Соединение потеряно, переподключение...")

    def _on_paired(self):
        """Получили ключ от сервера — прячемся в трей."""
        self.status_label.setText("✅ Зарегистрированы!")
        self.pair_status.setText("Устройство добавлено учителем.")
        self._heartbeat_timer.start(15_000)
        # Через секунду уходим в трей
        QTimer.singleShot(1500, self._go_to_tray)

    def _on_command(self, raw: str):
        key = self._cfg.get("key")
        if not key:
            return
        data = verify_and_parse(raw, key)
        if data is None:
            return  # подпись не прошла
        action = data.get("action")
        if action == "open_url":
            url = data.get("url", "")
            if url:
                webbrowser.open(url)

    # ------------------------------------------------------------------ #
    #  Трей                                                                #
    # ------------------------------------------------------------------ #
    def _go_to_tray(self):
        self.hide()
        if not hasattr(self, "_tray"):
            self._tray = QSystemTrayIcon(self)
            self._tray.setIcon(QIcon.fromTheme("computer",
                QIcon(self.style().standardIcon(self.style().SP_ComputerIcon))))
            menu = QMenu()
            act_quit = QAction("Выйти")
            act_quit.triggered.connect(QApplication.quit)
            menu.addAction(act_quit)
            self._tray.setContextMenu(menu)
            self._tray.setToolTip(f"Урок — {self._cfg.get('device_name', '?')}")
        self._tray.show()
        self._tray.showMessage(
            "Дистанционное управление",
            "Клиент работает в фоне. Учитель может отправлять команды.",
            QSystemTrayIcon.Information, 3000
        )

    def closeEvent(self, event):
        """Закрытие окна → в трей."""
        if self._cfg.get("key"):
            self._go_to_tray()
            event.ignore()
        else:
            event.accept()
