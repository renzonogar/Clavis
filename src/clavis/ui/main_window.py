"""
Clavis Main Window (PySide6)
Top-level application window managing navigation between Welcome, Unlock,
and Main Vault screens, session inactivity timer, and USB presence polling.
"""

from typing import Optional

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtGui import QCloseEvent, QCursor
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox, QLabel, QWidget

from ..vault import ClavisVault, VaultAuthenticationError, MalformedVaultError
from ..session import SessionManager
from ..storage import StorageError, DriveDisconnectedError, InsufficientSpaceError
from .welcome_view import WelcomeView
from .unlock_view import UnlockView
from .vault_view import VaultView


class MainWindow(QMainWindow):
    """Primary PySide6 Desktop Window for Clavis."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Your vault. Your device. Your control.")
        self.resize(900, 600)
        self.setMinimumSize(800, 550)

        # Global Dark Styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121316;
            }
            QStatusBar {
                background-color: #0d0e11;
                color: #9ca3af;
                font-size: 11px;
                border-top: 1px solid #1f222b;
            }
        """)

        self.vault = ClavisVault()
        self.session = SessionManager(self.vault, timeout_seconds=300)
        self._last_mouse_position = QCursor.pos()
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

        self._init_stack()
        self._init_status_bar()
        self._init_heartbeat_timer()

    def _init_stack(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Screen 0: Welcome
        self.welcome_view = WelcomeView()
        self.welcome_view.vault_create_requested.connect(self._on_prompt_create_vault)
        self.welcome_view.vault_open_requested.connect(self._on_prompt_open_vault)
        self.stack.addWidget(self.welcome_view)

        # Screen 1: Unlock / Password Setup
        self.unlock_view = UnlockView()
        self.unlock_view.unlock_submitted.connect(self._on_unlock_submitted)
        self.unlock_view.create_submitted.connect(self._on_create_submitted)
        self.unlock_view.back_requested.connect(self._on_back_to_welcome)
        self.stack.addWidget(self.unlock_view)

        # Screen 2: Vault (initialized dynamically upon unlock)
        self.vault_view: Optional[VaultView] = None

    def _init_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_offline = QLabel("● OFFLINE SYSTEM (No Network)")
        self.status_offline.setStyleSheet("color: #34d399; font-weight: 600; padding: 2px 8px;")
        self.status_bar.addPermanentWidget(self.status_offline)

        self.status_timer = QLabel("Auto-lock: 5m 00s")
        self.status_timer.setStyleSheet("color: #9ca3af; padding: 2px 8px;")
        self.status_bar.addPermanentWidget(self.status_timer)

    def _init_heartbeat_timer(self):
        # 1-second timer for timeout counting and USB disconnect monitoring
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self._on_heartbeat)
        self.heartbeat_timer.start(1000)

        self.session.on_locked(self._on_session_auto_locked)

    def eventFilter(self, watched, event):
        if (
            event.type() in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress)
            and isinstance(watched, QWidget)
            and (watched is self or self.isAncestorOf(watched))
        ):
            self.session.record_activity()
        return super().eventFilter(watched, event)

    def _replace_session(self, vault: ClavisVault):
        timeout_seconds = self.session.timeout_seconds
        self.session = SessionManager(vault, timeout_seconds)
        self.session.on_locked(self._on_session_auto_locked)

    def _on_heartbeat(self):
        if not self.vault.is_unlocked:
            self.status_timer.setText("Vault Locked")
            return

        mouse_position = QCursor.pos()
        if (
            self.isActiveWindow()
            and self.rect().contains(self.mapFromGlobal(mouse_position))
            and mouse_position != self._last_mouse_position
        ):
            self.session.record_activity()
        self._last_mouse_position = mouse_position

        # Check USB physical presence
        if not self.session.check_usb_presence():
            QMessageBox.critical(
                self,
                "USB Device Disconnected",
                "The USB drive containing the active vault was disconnected or removed. "
                "The vault has been locked immediately to protect sensitive credentials."
            )
            self._lock_and_show_welcome()
            return

        # Check inactivity timeout
        if self.session.check_inactivity():
            QMessageBox.information(
                self,
                "Session Timed Out",
                "Your vault has been locked due to inactivity."
            )
            return

        rem = self.session.get_remaining_seconds()
        if rem is not None:
            mins, secs = divmod(rem, 60)
            self.status_timer.setText(f"Auto-lock: {mins}m {secs:02d}s")
        else:
            self.status_timer.setText("Auto-lock: Disabled")

    def _on_prompt_create_vault(self, target_path: str):
        self.vault = ClavisVault(target_path)
        self._replace_session(self.vault)
        self.unlock_view.set_mode(is_creation=True, vault_path=target_path)
        self.stack.setCurrentIndex(1)

    def _on_prompt_open_vault(self, vault_path: str):
        self.vault = ClavisVault(vault_path)
        self._replace_session(self.vault)
        self.unlock_view.set_mode(is_creation=False, vault_path=vault_path)
        self.stack.setCurrentIndex(1)

    def _on_back_to_welcome(self):
        self.stack.setCurrentIndex(0)

    def _on_create_submitted(self, master_pw: str, confirm_pw: str):
        try:
            self.vault = ClavisVault.create_new(
                vault_path=self.unlock_view.target_vault_path,
                master_password=master_pw
            )
            self._replace_session(self.vault)
            self._transition_to_vault()
        except Exception as e:
            self.unlock_view.show_error(f"Failed to create encrypted vault: {e}")

    def _on_unlock_submitted(self, master_pw: str):
        try:
            self.vault.open_existing(master_pw)
            self._replace_session(self.vault)
            self._transition_to_vault()
        except VaultAuthenticationError:
            # Generic error to prevent leaking whether password, tag, or file caused it
            self.unlock_view.show_error("Authentication failed or vault is corrupted.")
        except MalformedVaultError as me:
            self.unlock_view.show_error(f"Invalid vault format: {me}")
        except StorageError as se:
            self.unlock_view.show_error(f"Storage error: {se}")
        except Exception:
            self.unlock_view.show_error("Authentication failed or vault is corrupted.")

    def _transition_to_vault(self):
        # Remove old vault view if any
        if self.vault_view:
            self.stack.removeWidget(self.vault_view)
            self.vault_view.deleteLater()

        self.vault_view = VaultView(self.vault)
        self.vault_view.lock_requested.connect(self._lock_and_show_welcome)
        self.vault_view.save_requested.connect(self._save_vault)
        self.vault_view.settings_view.timeout_changed.connect(self.session.set_timeout)
        self.vault_view.settings_view.master_password_change_requested.connect(self.vault.change_master_password)

        self.stack.addWidget(self.vault_view)
        self.stack.setCurrentWidget(self.vault_view)
        self.session.record_activity()

    def _save_vault(self):
        try:
            success, msg = self.vault.save(preserve_backup=True)
            if self.vault_view:
                self.vault_view.mark_saved()
            QMessageBox.information(self, "Vault Saved", msg)
        except DriveDisconnectedError as de:
            QMessageBox.critical(self, "USB Disconnected", str(de))
        except InsufficientSpaceError as ie:
            QMessageBox.critical(self, "Insufficient Space", str(ie))
        except StorageError as se:
            QMessageBox.critical(self, "Save Failed", str(se))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save vault: {e}")

    def _lock_and_show_welcome(self):
        if self.vault.has_unsaved_changes:
            ans = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes in your vault. Do you want to save them before locking?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            )
            if ans == QMessageBox.StandardButton.Save:
                try:
                    self.vault.save(preserve_backup=True)
                except Exception as e:
                    QMessageBox.warning(self, "Save Failed", f"Could not save changes: {e}")
                    return
            elif ans == QMessageBox.StandardButton.Cancel:
                return

        if self.vault_view:
            self.vault_view.clear_sensitive_clipboard()
        self.vault.lock()
        self.welcome_view.refresh_drives()
        self.stack.setCurrentIndex(0)

    def _on_session_auto_locked(self):
        if self.vault_view:
            self.vault_view.clear_sensitive_clipboard()
        self.welcome_view.refresh_drives()
        self.stack.setCurrentIndex(0)

    def closeEvent(self, event: QCloseEvent):
        if self.vault.is_unlocked and self.vault.has_unsaved_changes:
            ans = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes in your vault. Save before quitting?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            )
            if ans == QMessageBox.StandardButton.Save:
                try:
                    self.vault.save(preserve_backup=True)
                except Exception as e:
                    QMessageBox.critical(self, "Save Failed", f"Save failed: {e}. Aborting quit.")
                    event.ignore()
                    return
            elif ans == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        if self.vault_view:
            self.vault_view.clear_sensitive_clipboard()
        self.vault.lock()
        event.accept()
