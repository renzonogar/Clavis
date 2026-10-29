"""Screen scale detection and startup configuration for Qt's global UI scale."""

import ctypes
import os

from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication, QScreen


MIN_UI_SCALE = 80
MAX_UI_SCALE = 200
UI_SCALE_STEP = 5
_DPI_BASELINE = 96.0


def recommended_ui_scale(screen: QScreen | None = None) -> int:
    """Return a recommended percentage based on the screen's native Qt scale."""
    if screen is None:
        application = QGuiApplication.instance()
        if isinstance(application, QGuiApplication):
            screen = application.primaryScreen()

    scale_factor = screen.devicePixelRatio() if screen is not None else _native_scale_factor()
    applied_factor = _environment_scale_factor()
    if screen is not None:
        scale_factor /= applied_factor

    return _normalize_scale_percent(scale_factor * 100)


def configure_ui_scale_from_settings(settings: QSettings) -> None:
    """Set Qt's global scale before QApplication is created."""
    selected_scale = str(settings.value("ui/scale_percent", "recommended"))
    if selected_scale == "recommended":
        return

    try:
        target_percent = int(selected_scale)
    except ValueError as error:
        raise ValueError(f"Invalid saved UI scale: {selected_scale!r}") from error

    if not _is_supported_scale(target_percent):
        raise ValueError(f"Unsupported saved UI scale: {target_percent}%")

    scale_factor = _scale_factor_for_percent(
        target_percent, _native_scale_factor()
    )
    os.environ["QT_SCALE_FACTOR"] = f"{scale_factor:.4f}"


def _environment_scale_factor() -> float:
    raw_factor = os.environ.get("QT_SCALE_FACTOR")
    if raw_factor is None:
        return 1.0
    try:
        factor = float(raw_factor)
    except ValueError:
        return 1.0
    return factor if factor > 0 else 1.0


def _native_scale_factor() -> float:
    if os.name == "nt":
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()
        except (AttributeError, OSError):
            dpi = 0
        if dpi:
            return dpi / _DPI_BASELINE
    return 1.0


def _scale_factor_for_percent(target_percent: int, native_scale: float) -> float:
    return target_percent / (100 * native_scale)


def _normalize_scale_percent(percent: float) -> int:
    rounded = int(percent / 5 + 0.5) * 5
    return max(MIN_UI_SCALE, min(MAX_UI_SCALE, rounded))


def _is_supported_scale(percent: int) -> bool:
    return (
        MIN_UI_SCALE <= percent <= MAX_UI_SCALE
        and (percent - MIN_UI_SCALE) % UI_SCALE_STEP == 0
    )
