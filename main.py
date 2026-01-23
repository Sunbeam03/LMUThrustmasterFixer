# main.py
import sys
import ctypes
import os
from PyQt6.QtWidgets import QApplication
from gui import MainWindow
from styles import DARK_THEME


def is_admin():
    """Checks if the script has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def main():
    # 1. Admin Check
    if not is_admin():
        # Re-run the program with admin rights
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, __file__, None, 1
        )
        sys.exit(0)

    # 2. Setup Application
    app = QApplication(sys.argv)

    # Apply Styles
    app.setStyleSheet(DARK_THEME)

    # 3. Launch Window
    window = MainWindow()
    window.show()

    # 4. Execution Loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()