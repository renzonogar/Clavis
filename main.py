"""
Clavis — Portable Offline-First Password Manager
"Your vault. Your device. Your control."

Entry point for the PySide6 desktop application.
"""

import os
import sys

sys.dont_write_bytecode = True

# Ensure src is on python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def main():
    try:
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont, QIcon
        from clavis.ui.main_window import MainWindow
        from clavis.ui.ui_scale import configure_ui_scale_from_settings

        configure_ui_scale_from_settings(QSettings("Clavis", "Clavis"))
        app = QApplication(sys.argv)
        app.setApplicationName("Clavis")
        app.setApplicationDisplayName("Clavis")
        app_icon = QIcon(os.path.join(BASE_DIR, "assets", "favicon.png"))
        if app_icon.isNull():
            raise RuntimeError("Unable to load the Clavis application icon.")
        app.setWindowIcon(app_icon)

        # Set default font
        font = QFont("Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif", 10)
        app.setFont(font)

        window = MainWindow()
        window.setWindowIcon(app_icon)
        window.show()
        return app.exec()

    except ImportError as e:
        print("[!] PySide6 is not installed or GUI libraries are missing.")
        print("    Install dependencies via: pip install -r requirements.txt")
        print(f"    Detail: {e}")
        return 1
    except Exception as e:
        print(f"[!] Error launching Clavis: {e}")
        return 1
    finally:
        _remove_bytecode_cache()


def _remove_bytecode_cache():
    """Remove Python bytecode generated inside the application directory."""
    for current_dir, child_dirs, filenames in os.walk(BASE_DIR, topdown=True):
        for name in list(child_dirs):
            if name == "__pycache__":
                cache_dir = os.path.join(current_dir, name)
                if not os.path.islink(cache_dir):
                    try:
                        for filename in os.listdir(cache_dir):
                            if filename.endswith(".pyc"):
                                os.remove(os.path.join(cache_dir, filename))
                        if not os.listdir(cache_dir):
                            os.rmdir(cache_dir)
                    except OSError as error:
                        print(
                            f"[!] Could not completely remove bytecode cache "
                            f"'{cache_dir}': {error}",
                            file=sys.stderr,
                        )
        child_dirs[:] = [
            name for name in child_dirs
            if name != "__pycache__" and not os.path.islink(
                os.path.join(current_dir, name)
            )
        ]


if __name__ == "__main__":
    sys.exit(main())
