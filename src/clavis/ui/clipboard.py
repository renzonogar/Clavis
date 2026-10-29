"""Temporary clipboard handling for copied passwords."""

from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication


class ClipboardAutoClear(QObject):
    """Clears a copied password after a delay unless the clipboard changed."""

    copied = Signal()
    timer_finished = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._clipboard = QGuiApplication.clipboard()
        self._copied_text: Optional[str] = None
        self._timeout_seconds = 30
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(30_000)
        self._timer.timeout.connect(self.clear_if_unchanged)

    def copy_password(self, password: str) -> bool:
        if not password:
            return False
        self._copied_text = password
        self._clipboard.setText(password)
        if self._timeout_seconds > 0:
            self._timer.start(self._timeout_seconds * 1000)
        self.copied.emit()
        return True

    def set_timeout_seconds(self, seconds: int) -> None:
        self._timeout_seconds = max(0, seconds)
        self._timer.stop()
        if self._timeout_seconds > 0 and self._copied_text is not None:
            self._timer.start(self._timeout_seconds * 1000)

    @property
    def timeout_seconds(self) -> int:
        return self._timeout_seconds

    def clear_if_unchanged(self) -> None:
        self._timer.stop()
        copied_text = self._copied_text
        self._copied_text = None
        if copied_text is not None and self._clipboard.text() == copied_text:
            self._clipboard.clear()
        self.timer_finished.emit()
