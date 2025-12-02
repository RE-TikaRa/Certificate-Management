from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .app_context import bootstrap
from .ui.main_window import MainWindow


def main(debug: bool = False) -> None:
    app = QApplication(sys.argv)
    ctx = bootstrap(debug=debug)
    window = MainWindow(ctx)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
