"""Helpers for loading bundled Clavis icons."""

from pathlib import Path

from PySide6.QtGui import QIcon


ICON_DIR = Path(__file__).resolve().parents[3] / "assets" / "icons"


def load_icon(name: str) -> QIcon:
    """Load a bundled SVG icon and report missing or unreadable assets."""
    icon_path = ICON_DIR / name
    if not icon_path.is_file():
        raise FileNotFoundError(f"Clavis icon not found: {icon_path}")

    icon = QIcon(str(icon_path))
    if icon.isNull():
        raise RuntimeError(f"Unable to load Clavis icon: {icon_path}")
    return icon
