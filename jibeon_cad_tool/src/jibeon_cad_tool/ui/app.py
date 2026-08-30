import sys

from PySide6.QtWidgets import QApplication

from ..env import load_env
from .main_window import MainWindow


def build_application(show: bool = True) -> tuple[QApplication, MainWindow]:
    load_env()
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    if show:
        window.show()
    return app, window


def main() -> int:
    app, _window = build_application(show=True)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
