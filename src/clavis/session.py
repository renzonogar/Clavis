"""
Clavis Session Manager
Inactivity timeout tracking, USB presence monitoring, and automatic locking.
"""

import time
from typing import Callable, List, Optional
from .vault import ClavisVault
from .storage import SafeVaultStorage


class SessionManager:
    """
    Manages user session activity, inactivity timer countdown,
    USB presence verification, and automatic vault locking.
    """
    DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes

    def __init__(self, vault: ClavisVault, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        self.vault = vault
        self.timeout_seconds = timeout_seconds  # 0 means disabled
        self.last_activity_time = time.time()
        self._lock_listeners: List[Callable[[], None]] = []
        self._warning_listeners: List[Callable[[int], None]] = []
        self._usb_disconnect_listeners: List[Callable[[], None]] = []

    def record_activity(self) -> None:
        """Resets the inactivity timer upon user input."""
        self.last_activity_time = time.time()

    def set_timeout(self, seconds: int) -> None:
        """Configures inactivity timeout duration in seconds (0 = never lock)."""
        self.timeout_seconds = max(0, seconds)
        self.record_activity()

    def get_remaining_seconds(self) -> Optional[int]:
        """Returns seconds remaining before automatic timeout lock, or None if disabled."""
        if self.timeout_seconds <= 0 or not self.vault.is_unlocked:
            return None
        elapsed = time.time() - self.last_activity_time
        remaining = self.timeout_seconds - elapsed
        return max(0, int(remaining))

    def check_inactivity(self) -> bool:
        """
        Evaluates elapsed idle time. If timeout has expired, locks the vault.
        Returns True if the vault was locked due to timeout.
        """
        if not self.vault.is_unlocked or self.timeout_seconds <= 0:
            return False

        elapsed = time.time() - self.last_activity_time
        if elapsed >= self.timeout_seconds:
            self.lock_now("Inactivity timeout reached.")
            return True
        return False

    def check_usb_presence(self) -> bool:
        """
        Verifies that the USB drive or directory where the vault resides is still connected.
        If removed, triggers alert and locks immediately to protect in-memory data.
        """
        if not self.vault.is_unlocked or not self.vault.vault_path:
            return True

        if not SafeVaultStorage.check_drive_accessible(self.vault.vault_path):
            for cb in self._usb_disconnect_listeners:
                try:
                    cb()
                except Exception:
                    pass
            self.lock_now("USB device was disconnected while unlocked.")
            return False
        return True

    def lock_now(self, reason: str = "User locked") -> None:
        """Locks the vault immediately and notifies all registered UI listeners."""
        if self.vault.is_unlocked:
            self.vault.lock()
            for cb in self._lock_listeners:
                try:
                    cb()
                except Exception:
                    pass

    def on_locked(self, callback: Callable[[], None]) -> None:
        self._lock_listeners.append(callback)

    def on_usb_disconnected(self, callback: Callable[[], None]) -> None:
        self._usb_disconnect_listeners.append(callback)
