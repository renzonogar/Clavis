"""
Clavis — Portable Offline-First Password Manager
"Your vault. Your device. Your control."

Entry point for the PySide6 desktop application.
"""

import os
import sys

# Ensure src is on python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def main():
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont
        from clavis.ui.main_window import MainWindow

        app = QApplication(sys.argv)
        app.setApplicationName("Clavis")
        app.setApplicationDisplayName("Clavis — Offline-First Encrypted Vault")

        # Set default font
        font = QFont("Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif", 10)
        app.setFont(font)

        window = MainWindow()
        window.show()
        sys.exit(app.exec())

    except ImportError as e:
        print("[!] PySide6 is not installed or GUI libraries are missing.")
        print("    Install dependencies via: pip install -r requirements.txt")
        print(f"    Detail: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[!] Error launching Clavis: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
