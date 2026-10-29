import os
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from clavis.ui.ui_scale import (
    MAX_UI_SCALE,
    MIN_UI_SCALE,
    _native_scale_factor,
    configure_ui_scale_from_settings,
    recommended_ui_scale,
)


class FakeScreen:
    def __init__(self, device_pixel_ratio: float):
        self._device_pixel_ratio = device_pixel_ratio

    def devicePixelRatio(self) -> float:
        return self._device_pixel_ratio


@pytest.mark.parametrize(
    ("device_pixel_ratio", "expected"),
    (
        (0.75, MIN_UI_SCALE),
        (1.03, 105),
        (1.25, 125),
        (1.75, 175),
        (2.5, MAX_UI_SCALE),
    ),
)
def test_recommended_ui_scale_uses_screen_scale(device_pixel_ratio, expected):
    assert recommended_ui_scale(FakeScreen(device_pixel_ratio)) == expected


def test_recommended_ui_scale_excludes_clavis_override(monkeypatch):
    monkeypatch.setenv("QT_SCALE_FACTOR", "1.25")
    assert recommended_ui_scale(FakeScreen(1.875)) == 150


def test_configure_ui_scale_from_settings_sets_qt_scale_before_startup(
    tmp_path, monkeypatch
):
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    settings.setValue("ui/scale_percent", "125")
    monkeypatch.delenv("QT_SCALE_FACTOR", raising=False)

    configure_ui_scale_from_settings(settings)

    expected = 125 / (100 * _native_scale_factor())
    assert float(os.environ["QT_SCALE_FACTOR"]) == pytest.approx(
        expected, abs=0.0001
    )


def test_configure_ui_scale_rejects_unsupported_saved_value(tmp_path):
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    settings.setValue("ui/scale_percent", "125.5")

    with pytest.raises(ValueError, match="Invalid saved UI scale"):
        configure_ui_scale_from_settings(settings)
