"""
Главное окно учителя:
  - Отображает сгенерированный ключ
  - Список клиентов в ожидании спаривания
  - Плиточное меню: Управление | Передача | ...
  - Диалог отправки URL
"""

import json
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QClipboard
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QListWidget, QListWidgetItem, QDialog,
    QLineEdit, QMessageBox, QSplitter, QFrame,
    QApplication, QScrollArea, QStackedWidget,
)

from config import load_config, save_config
from mqtt_handler import MQTTHandler
from crypto_utils import generate_server_key, key_to_display, sign_payload


# ─────────────────────────────────────────────────────────────
#  Стили
# ─────────────────────────────────────────────────────────────
DARK_BG   = "#1e1e2e"
SURFACE   = "#313244"
SURFACE2  = "#45475a"
TEXT      = "#cdd6f4"
SUBTEXT   = "#a6adc8"
ACCENT    = "#cba6f7"
BLUE      = "#89b4fa"
GREEN     = "#a6e3a1"
YELLOW    = "#f9e2af"
RED       = "#f38ba8"


BASE_STYLE = f"""
QMainWindow, QWidget {{ background:{DARK_BG}; color:{TEXT}; font-family:'Segoe UI'; }}
QLabel {{ color:{TEXT}; }}
QPushButton {{
    background:{SURFACE}; color:{TEXT}; border:none; border-radius:10px;
    padding:8px 16px; font-size:13px;
}}
QPushButton:hover {{ background:{SURFACE2}; }}
QListWidget {{
    background:{SURFACE}; border:1px solid {SURFACE2}; border-radius:8px;
    color:{TEXT}; font-size:13px;
}}
QListWidget::item:selected {{ background:{ACCENT}; color:{DARK_BG}; }}
QLineEdit {{
    background:{SURFACE}; border:1px solid {SURFACE2}; border-radius:8px;
    padding:6px 12px; color:{TEXT}; font-size:13px;
}}
QLineEdit:focus {{ border-color:{BLUE}; }}
"""


# ─────────────────────────────────────────────────────────────
#  Tile Button
# ─────────────────────────────────────────────────────────────
def make_tile(emoji: str, title: str, subtitle: str,
              accent: str = BLUE, enabled: bool = True,
              size: int = 160) -> QPushButton:
    btn = QPushButton(f"{emoji}\n{title}\n{subtitle}")
    btn.setFixedSize(size, size)
    btn.setFont(QFont("Segoe UI", 11))
    btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
    color = accent if enabled else SURFACE2
    text_color = DARK_BG if enabled else SUBTEXT
    btn.setStyleSheet(f"""
        QPushButton {{
            background:{SURFACE};
            color:{color};
            border:2px solid {color};
            border-radius:16px;
            text-align:center;
        }}
        QPushButton:hover {{
            background:{color if enabled else SURFACE};
            color:{text_color};
        }}
    """)
    btn.setEnabled(enabled)
    return btn


# ─────────────────────────────────────────────────────────────
#  Сигналы (thread-safe)
# ─────────────────────────────────────────────────────────────
class _Signals(QObject):
    announced    = pyqtSignal(str, str)   # device_name, client_id
    heartbeat    = pyqtSignal(str, str)   # device_name, client_id
    conn_changed = pyqtSignal(bool)


# ─────────────────────────────────────────────────────────────
#  Диалог «Открыть ссылку»
# ─────────────────────────────────────────────────────────────
class SendUrlDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Отправить ссылку")
        self.setFixedSize(420, 180)
        self.setStyleSheet(f"background:{DARK_BG}; color:{TEXT};")
        self.url = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        lay.addWidget(QLabel("Ссылка откроется в браузере у всех подключённых учеников:"))

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("https://...")
        lay.addWidget(self.edit)

        btn = QPushButton("🚀  Отправить")
        btn.setFixedHeight(40)
        btn.setStyleSheet(f"""
            QPushButton {{ background:{GREEN}; color:{DARK_BG}; border-radius:10px;
                           font-weight:bold; font-size:13px; }}
            QPushButton:hover {{ background:#c3fac0; }}
        """)
        btn.clicked.connect(self._send)
        lay.addWidget(btn)

    def _send(self):
        url = self.edit.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            url = "https://" + url
        self.url = url
        self.accept()


# ─────────────────────────────────────────────────────────────
#  Главное окно
# ─────────────────────────────────────────────────────────────
class ServerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Дистанционное управление — Учитель")
        self.setMinimumSize(860, 580)
        self.setStyleSheet(BASE_STYLE)

        self._cfg = load_config()
        # Генерируем ключ один раз
        if not self._cfg.get("key"):
            self._cfg["key"] = generate_server_key()
            save_config(self._cfg)

        self._signals = _Signals()
        self._signals.announced.connect(self._on_client_announced)
        self._signals.heartbeat.connect(self._on_heartbeat)
        self._signals.conn_changed.connect(self._on_conn_changed)

        self._mqtt: MQTTHandler | None = None
        # client_id -> {"device_name", "status": "waiting"|"paired"|"online"}
        self._clients: dict[str, dict] = {}

        self._online_timer = QTimer()
        self._online_timer.timeout.connect(self._prune_offline)
        self._last_seen: dict[str, float] = {}

        self._build_ui()
        self._load_paired_clients()
        self._connect_mqtt()

    # ─────────────────────────────────────────────────────────
    #  UI
    # ─────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Боковая панель ──────────────────────────────── #
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(f"background:{SURFACE}; border-right:1px solid {SURFACE2};")
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(16, 20, 16, 16)
        sl.setSpacing(8)

        logo = QLabel("🖥️  Учитель")
        logo.setFont(QFont("Segoe UI", 14, QFont.Bold))
        sl.addWidget(logo)

        key_title = QLabel("Ключ класса:")
        key_title.setStyleSheet(f"color:{SUBTEXT}; font-size:11px; margin-top:12px;")
        sl.addWidget(key_title)

        display_key = key_to_display(self._cfg["key"])
        key_lbl = QLabel(display_key)
        key_lbl.setFont(QFont("Consolas", 13, QFont.Bold))
        key_lbl.setStyleSheet(f"color:{ACCENT}; letter-spacing:2px;")
        key_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        sl.addWidget(key_lbl)

        sl.addSpacing(16)
        conn_title = QLabel("Статус:")
        conn_title.setStyleSheet(f"color:{SUBTEXT}; font-size:11px;")
        sl.addWidget(conn_title)
        self.conn_label = QLabel("⏳ Подключение...")
        self.conn_label.setStyleSheet(f"color:{YELLOW}; font-size:12px;")
        sl.addWidget(self.conn_label)

        sl.addSpacing(20)
        nav_title = QLabel("НАВИГАЦИЯ")
        nav_title.setStyleSheet(f"color:{SUBTEXT}; font-size:10px; letter-spacing:1px;")
        sl.addWidget(nav_title)

        self._nav_btns = {}
        nav_items = [
            ("clients",  "👥  Ученики"),
            ("transfer", "📤  Передача"),
        ]
        for key, label in nav_items:
            btn = QPushButton(label)
            btn.setFixedHeight(38)
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{TEXT}; text-align:left;
                               padding-left:8px; border-radius:8px; font-size:13px; }}
                QPushButton:checked {{ background:{SURFACE2}; color:{ACCENT}; }}
                QPushButton:hover {{ background:{SURFACE2}; }}
            """)
            btn.clicked.connect(lambda _, k=key: self._nav(k))
            self._nav_btns[key] = btn
            sl.addWidget(btn)

        sl.addStretch()
        root.addWidget(sidebar)

        # ── Основной контент ────────────────────────────── #
        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_clients_page())   # 0
        self._stack.addWidget(self._build_transfer_page())  # 1

        self._nav("clients")

    def _nav(self, key: str):
        pages = {"clients": 0, "transfer": 1}
        self._stack.setCurrentIndex(pages.get(key, 0))
        for k, btn in self._nav_btns.items():
            btn.setChecked(k == key)

    # ── Страница «Ученики» ──────────────────────────────── #
    def _build_clients_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        hdr = QLabel("👥  Управление учениками")
        hdr.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lay.addWidget(hdr)

        sub = QLabel("Ожидающие — клиенты, которые ещё не получили ключ. "
                     "Выберите и нажмите «Добавить».")
        sub.setStyleSheet(f"color:{SUBTEXT}; font-size:12px;")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        # Списки
        lists_row = QHBoxLayout()

        wait_col = QVBoxLayout()
        wait_col.addWidget(self._section_label("⏳  Ожидают добавления"))
        self.waiting_list = QListWidget()
        self.waiting_list.setMinimumHeight(200)
        wait_col.addWidget(self.waiting_list)

        add_btn = QPushButton("✅  Добавить выбранных")
        add_btn.setFixedHeight(38)
        add_btn.setStyleSheet(f"""
            QPushButton {{ background:{GREEN}; color:{DARK_BG};
                           border-radius:10px; font-weight:bold; }}
            QPushButton:hover {{ background:#c3fac0; }}
        """)
        add_btn.clicked.connect(self._pair_selected)
        wait_col.addWidget(add_btn)
        lists_row.addLayout(wait_col)

        online_col = QVBoxLayout()
        online_col.addWidget(self._section_label("🟢  Подключённые ученики"))
        self.online_list = QListWidget()
        self.online_list.setMinimumHeight(200)
        online_col.addWidget(self.online_list)
        lists_row.addLayout(online_col)

        lay.addLayout(lists_row)
        lay.addStretch()
        return page

    # ── Страница «Передача» ─────────────────────────────── #
    def _build_transfer_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        hdr = QLabel("📤  Передача")
        hdr.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lay.addWidget(hdr)

        sub = QLabel("Отправьте ссылку или материал всем подключённым ученикам.")
        sub.setStyleSheet(f"color:{SUBTEXT}; font-size:12px;")
        lay.addWidget(sub)

        grid = QGridLayout()
        grid.setSpacing(16)

        # ── Активные плитки ─────────────── #
        tile_url = make_tile("🌐", "Открыть ссылку",
                             "Откроется у всех", accent=GREEN, enabled=True)
        tile_url.clicked.connect(self._send_url)
        grid.addWidget(tile_url, 0, 0)

        # ── Будущие плитки ──────────────── #
        future = [
            ("📁", "Файлы", "Скоро"),
            ("🗂️", "Рабочая область", "Скоро"),
            ("📊", "Экран учителя", "Скоро"),
            ("🔒", "Заблокировать ПК", "Скоро"),
            ("📝", "Задание", "Скоро"),
        ]
        pos = [(0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]
        for (e, t, s), (r, c) in zip(future, pos):
            grid.addWidget(make_tile(e, t, s, accent=SUBTEXT, enabled=False), r, c)

        lay.addLayout(grid)
        lay.addStretch()
        return page

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{SUBTEXT}; font-size:11px; margin-bottom:4px;")
        return lbl

    # ─────────────────────────────────────────────────────────
    #  MQTT
    # ─────────────────────────────────────────────────────────
    def _connect_mqtt(self):
        self._mqtt = MQTTHandler("server-" + self._cfg["key"][:8])
        self._mqtt.on_connection_change = lambda ok: self._signals.conn_changed.emit(ok)
        self._mqtt.on_announce = lambda d: self._signals.announced.emit(
            d.get("device_name", "?"), d.get("client_id", ""))
        self._mqtt.on_heartbeat = lambda d: self._signals.heartbeat.emit(
            d.get("device_name", "?"), d.get("client_id", ""))
        self._mqtt.setup_as_server()
        self._mqtt.connect()

    # ─────────────────────────────────────────────────────────
    #  Обработчики сигналов (UI-поток)
    # ─────────────────────────────────────────────────────────
    def _on_conn_changed(self, ok: bool):
        if ok:
            self.conn_label.setText("🟢 Онлайн")
            self.conn_label.setStyleSheet(f"color:{GREEN}; font-size:12px;")
        else:
            self.conn_label.setText("🔴 Нет связи")
            self.conn_label.setStyleSheet(f"color:{RED}; font-size:12px;")

    def _on_client_announced(self, device_name: str, client_id: str):
        if not client_id:
            return
        if client_id not in self._clients:
            self._clients[client_id] = {
                "device_name": device_name,
                "status": "waiting",
            }
            item = QListWidgetItem(f"  {device_name}")
            item.setData(Qt.UserRole, client_id)
            self.waiting_list.addItem(item)
        else:
            # Обновляем имя, если поменялось
            self._clients[client_id]["device_name"] = device_name
            self._refresh_online_list()

    def _on_heartbeat(self, device_name: str, client_id: str):
        import time
        self._last_seen[client_id] = time.time()
        if client_id not in self._clients:
            # Если пришёл heartbeat от ранее неизвестного клиента — считаем его спаренным
            self._clients[client_id] = {
                "device_name": device_name,
                "status": "online",
            }
            self._add_online_item(client_id)
            self._persist_paired_client(client_id)
        else:
            self._clients[client_id]["status"] = "online"
            self._clients[client_id]["device_name"] = device_name
            self._refresh_online_list()

    def _pair_selected(self):
        selected = self.waiting_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "Выберите ученика",
                                    "Выберите хотя бы одного ученика в списке ожидания.")
            return
        key = self._cfg["key"]
        for item in selected:
            client_id = item.data(Qt.UserRole)
            self._mqtt.publish_key_to_client(client_id, key)
            self._clients[client_id]["status"] = "paired"
            row = self.waiting_list.row(item)
            self.waiting_list.takeItem(row)
            # Добавляем в список подключённых
            self._add_online_item(client_id)
            self._persist_paired_client(client_id)

    def _refresh_online_list(self):
        for i in range(self.online_list.count()):
            item = self.online_list.item(i)
            client_id = item.data(Qt.UserRole)
            name = self._clients.get(client_id, {}).get("device_name", "?")
            status = self._clients.get(client_id, {}).get("status", "paired")
            icon = "🟢" if status == "online" else "🔑"
            item.setText(f"  {icon} {name}")

    def _add_online_item(self, client_id: str):
        name = self._clients.get(client_id, {}).get("device_name", "?")
        li = QListWidgetItem(f"  🔑 {name}")
        li.setData(Qt.UserRole, client_id)
        self.online_list.addItem(li)

    def _load_paired_clients(self):
        paired = self._cfg.get("paired_clients", [])
        for entry in paired:
            client_id = entry.get("client_id")
            name = entry.get("device_name", "?")
            if not client_id:
                continue
            self._clients[client_id] = {
                "device_name": name,
                "status": "paired",
            }
            self._add_online_item(client_id)

    def _persist_paired_client(self, client_id: str):
        name = self._clients.get(client_id, {}).get("device_name", "?")
        paired = self._cfg.get("paired_clients", [])
        # Удаляем старую запись, если есть
        paired = [p for p in paired if p.get("client_id") != client_id]
        paired.append({"client_id": client_id, "device_name": name})
        self._cfg["paired_clients"] = paired
        save_config(self._cfg)

    def _prune_offline(self):
        import time
        now = time.time()
        for cid, ts in list(self._last_seen.items()):
            if now - ts > 45:
                if cid in self._clients:
                    self._clients[cid]["status"] = "paired"
        self._refresh_online_list()

    # ─────────────────────────────────────────────────────────
    #  Команды
    # ─────────────────────────────────────────────────────────
    def _send_url(self):
        dlg = SendUrlDialog(self)
        if dlg.exec_() != QDialog.Accepted or not dlg.url:
            return
        try:
            if not self._mqtt:
                raise RuntimeError("MQTT не инициализирован")
            key = self._cfg.get("key")
            if not key:
                raise RuntimeError("Ключ сервера не найден")
            payload = {"action": "open_url", "url": dlg.url}
            msg = sign_payload(payload, key)
            self._mqtt.publish_command(msg)
            QMessageBox.information(
                self, "Отправлено",
                f"Ссылка отправлена всем ученикам:\n{dlg.url}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось отправить:\n{e}")
