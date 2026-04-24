"""
Окно первого запуска: выбор роли (сервер / клиент).
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget,
)


class RoleSelectDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Дистанционное управление — первый запуск")
        self.setFixedSize(520, 280)
        self.setStyleSheet("background:#1e1e2e; color:#cdd6f4;")
        self.role = None  # "server" | "client"
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(20)

        title = QLabel("Кто это устройство?")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        sub = QLabel("Выберите роль. Настройка выполняется один раз.")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:#a6adc8; font-size:12px;")
        root.addWidget(sub)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        self.btn_server = self._make_tile(
            "🖥️  Учитель\n(Сервер)",
            "#313244",
            "#cba6f7",
        )
        self.btn_client = self._make_tile(
            "🎒  Ученик\n(Клиент)",
            "#313244",
            "#89b4fa",
        )

        self.btn_server.clicked.connect(lambda: self._choose("server"))
        self.btn_client.clicked.connect(lambda: self._choose("client"))

        btn_row.addWidget(self.btn_server)
        btn_row.addWidget(self.btn_client)
        root.addLayout(btn_row)

    def _make_tile(self, text: str, bg: str, accent: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(200, 100)
        btn.setFont(QFont("Segoe UI", 13))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {accent};
                border: 2px solid {accent};
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background: {accent};
                color: #1e1e2e;
            }}
        """)
        return btn

    def _choose(self, role: str):
        self.role = role
        self.accept()
