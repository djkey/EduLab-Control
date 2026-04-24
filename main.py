"""
Точка входа.
"""

import os
import sys

# Фикс: явно указываем путь к Qt-плагинам внутри venv / site-packages
# (необходимо до импорта QApplication)
try:
    import PyQt5
    _qt_plugins = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
    if os.path.isdir(_qt_plugins):
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", _qt_plugins)
except Exception:
    pass

from PyQt5.QtWidgets import QApplication

from config import is_first_run, load_config, save_config, new_client_id
from crypto_utils import generate_server_key, key_to_display
from ui_role_select import RoleSelectDialog


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Дистанционное управление")

    if is_first_run():
        dlg = RoleSelectDialog()
        if dlg.exec_() != dlg.Accepted or dlg.role is None:
            sys.exit(0)

        role = dlg.role
        cfg: dict = {"role": role}

        if role == "server":
            cfg["key"] = generate_server_key()
            cfg["display_key"] = key_to_display(cfg["key"])
        else:
            cfg["client_id"] = new_client_id()

        save_config(cfg)
    else:
        cfg = load_config()
        role = cfg.get("role", "client")

    if role == "server":
        from ui_server import ServerWindow
        win = ServerWindow()
        win.show()
    else:
        from ui_client import ClientWindow
        win = ClientWindow()
        win.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
