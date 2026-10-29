"""
Clavis Main Window (PySide6)
Top-level application window managing navigation between Welcome, Unlock,
and Main Vault screens, session inactivity timer, and USB presence polling.
"""

from typing import Optional
from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, QSettings
from PySide6.QtGui import QCloseEvent, QCursor, QKeySequence, QShortcut, QIcon, QFont, QGuiApplication
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox, QLabel, QWidget, QFileDialog

from ..vault import ClavisVault, VaultAuthenticationError, MalformedVaultError, LegacyVaultFormatError
from ..session import SessionManager
from ..storage import StorageError, DriveDisconnectedError, InsufficientSpaceError
from .welcome_view import WelcomeView
from .unlock_view import UnlockView
from .vault_view import VaultView
from .i18n import (
    set_language,
    current_language,
    tr,
    apply_translations,
    set_translated_text,
)


class MainWindow(QMainWindow):
    """Primary PySide6 Desktop Window for Clavis."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clavis — Cofre local de senhas")
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1240, 780)
        else:
            available = screen.availableGeometry()
            available_width = max(600, available.width() - 48)
            available_height = max(400, available.height() - 48)
            self.resize(
                min(1240, available_width),
                min(780, available_height),
            )
            self.setMinimumSize(
                min(1000, available_width),
                min(640, available_height),
            )
        if screen is None:
            self.setMinimumSize(1000, 640)
        self.ui_settings = QSettings("Clavis", "Clavis")
        set_language(str(self.ui_settings.value("interface/language", "en")))
        self.setWindowTitle(tr("Clavis — Cofre local de senhas"))
        icon_path = Path(__file__).resolve().parents[3] / "assets" / "favicon.png"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Global Dark Styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #08090a;
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
        apply_translations(self, current_language())

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
        self.status_vault = QLabel("LOCAL VAULT")
        self.status_vault.setStyleSheet("color:#00e59b; font-family:Consolas,monospace; font-weight:700; padding:2px 8px;")
        self.status_bar.addPermanentWidget(self.status_vault)

        self.status_timer = QLabel("Cofre bloqueado")
        self.status_timer.setStyleSheet("color:#596875; font-family:Consolas,monospace; padding:2px 8px;")
        self.status_bar.addPermanentWidget(self.status_timer)
        self.status_save = QLabel("Sem alterações")
        self.status_save.setStyleSheet("color:#91a0ad; padding:2px 8px;")
        self.status_bar.addPermanentWidget(self.status_save)
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        shortcuts = (
            ("Ctrl+N", self._shortcut_new_credential),
            ("Ctrl+F", self._shortcut_search),
            ("Ctrl+L", self._lock_and_show_welcome),
            ("Ctrl+E", self._request_safe_eject),
            ("Alt+C", self._shortcut_copy_password),
        )
        for key, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)

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
            self.status_timer.setText(tr("Cofre bloqueado"))
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
                tr("Unidade desconectada"),
                tr("A unidade do cofre foi removida ou ficou inacessível. A sessão foi bloqueada; alterações ainda não salvas podem ter sido perdidas.")
            )
            return

        # Check inactivity timeout
        if self.session.get_remaining_seconds() == 0 and self.vault.has_unsaved_changes:
            try:
                self._save_current_vault()
                if self.vault_view:
                    self.vault_view.mark_saved()
            except Exception as error:
                self.session.record_activity()
                QMessageBox.warning(
                    self, tr("Falha ao salvar"),
                    tr("O bloqueio automático foi adiado para evitar perder alterações: {error}", error=error),
                )
                return

        if self.session.check_inactivity():
            QMessageBox.information(
                self,
                tr("Sessão encerrada"),
                tr("O cofre foi bloqueado por inatividade.")
            )
            return

        rem = self.session.get_remaining_seconds()
        if rem is not None:
            mins, secs = divmod(rem, 60)
            self.status_timer.setText(tr("Bloqueio em: {minutes}m {seconds:02d}s", minutes=mins, seconds=secs))
        else:
            self.status_timer.setText(tr("Bloqueio automático desativado"))

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
                self.unlock_view.target_vault_path, master_pw
            )
            self._replace_session(self.vault)
            self._transition_to_vault()
        except Exception as e:
            self.unlock_view.show_error(tr("Falha ao criar o cofre KDBX: {error}", error=e))

    def _on_unlock_submitted(self, master_pw: str):
        try:
            self.vault.open_existing(master_pw)
            self._replace_session(self.vault)
            self._transition_to_vault()
        except VaultAuthenticationError:
            # Generic error to prevent leaking whether password, tag, or file caused it
            self.unlock_view.show_error(tr("Senha incorreta ou cofre inválido."))
        except MalformedVaultError as me:
            self.unlock_view.show_error(tr("Formato de cofre inválido: {error}", error=me))
        except LegacyVaultFormatError:
            self._offer_legacy_import(master_pw)
        except StorageError as se:
            self.unlock_view.show_error(tr("Erro de armazenamento: {error}", error=se))
        except Exception:
            self.unlock_view.show_error(tr("Não foi possível abrir o cofre. Verifique a senha e o arquivo."))

    def _offer_legacy_import(self, master_pw: str):
        answer = QMessageBox.question(
            self,
            tr("Importar cofre antigo"),
            tr("Este arquivo usa o formato antigo do Clavis. Deseja convertê-lo para "
               "KDBX, mantendo o arquivo original intacto?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.unlock_view.show_error(
                tr("O cofre antigo precisa ser importado para KDBX.")
            )
            return
        default_path = self.vault.path.rsplit(".", 1)[0] + "-importado.vault"
        destination, _ = QFileDialog.getSaveFileName(
            self, tr("Salvar novo cofre KDBX"), default_path,
            tr("Clavis Vault (*.vault)")
        )
        if not destination:
            return
        try:
            self.vault = ClavisVault.import_legacy(
                self.vault.path, destination, master_pw
            )
            self._replace_session(self.vault)
            self._transition_to_vault()
        except Exception as error:
            self.unlock_view.show_error(
                tr("Falha ao importar o cofre: {error}", error=error)
            )

    def _transition_to_vault(self):
        # Remove old vault view if any
        if self.vault_view:
            self.stack.removeWidget(self.vault_view)
            self.vault_view.deleteLater()

        self.vault_view = VaultView(self.vault)
        self.vault_view.lock_requested.connect(self._lock_and_show_welcome)
        self.vault_view.save_requested.connect(self._save_vault)
        self.vault_view.eject_requested.connect(self._request_safe_eject)
        self.vault_view.settings_view.timeout_changed.connect(self.session.set_timeout)
        self.vault_view.settings_view.clipboard_timeout_changed.connect(
            self.vault_view.clipboard_auto_clear.set_timeout_seconds
        )
        self.vault_view.settings_view.font_size_changed.connect(self._apply_font_size)
        self.vault_view.settings_view.master_password_change_requested.connect(
            self._change_master_password
        )
        self.vault_view.settings_view.language_changed.connect(self._on_language_changed)
        self.session.set_timeout(self.vault_view.settings_view.timeout_seconds)
        self._apply_font_size(self.vault_view.settings_view.font_size)
        self.vault_view.clipboard_auto_clear.set_timeout_seconds(
            self.vault_view.settings_view.clipboard_timeout_seconds
        )

        self.stack.addWidget(self.vault_view)
        self.stack.setCurrentWidget(self.vault_view)
        self.session.record_activity()
        apply_translations(self, current_language())

    def _save_vault(self):
        try:
            _, msg = self._save_current_vault()
            if self.vault_view:
                self.vault_view.mark_saved()
            set_translated_text(self.status_save, "Cofre salvo")
            QMessageBox.information(self, tr("Cofre salvo"), msg)
        except DriveDisconnectedError as de:
            QMessageBox.critical(self, tr("Unidade desconectada"), str(de))
        except InsufficientSpaceError as ie:
            QMessageBox.critical(self, tr("Espaço insuficiente"), str(ie))
        except StorageError as se:
            QMessageBox.critical(self, tr("Falha ao salvar"), str(se))
        except Exception as e:
            QMessageBox.critical(self, tr("Erro"), tr("Falha ao salvar o cofre: {error}", error=e))

    def _change_master_password(self, password: str):
        try:
            self.vault.change_master_password(password)
            if self.vault_view:
                self.vault_view.mark_saved()
            set_translated_text(
                self.status_save, "Senha mestra alterada e cofre salvo"
            )
        except Exception as error:
            QMessageBox.critical(
                self, tr("Falha ao alterar senha mestra"),
                tr("A senha mestra não pôde ser salva: {error}", error=error),
            )

    def _lock_and_show_welcome(self):
        if self.vault.has_unsaved_changes:
            ans = QMessageBox.question(
                self,
                tr("Alterações não salvas"),
                tr("Há alterações não salvas. Deseja salvar antes de bloquear o cofre?"),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            )
            if ans == QMessageBox.StandardButton.Save:
                try:
                    self._save_current_vault()
                except Exception as e:
                    QMessageBox.warning(
                        self, tr("Falha ao salvar"),
                        tr("Não foi possível salvar as alterações: {error}", error=e),
                    )
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
                tr("Alterações não salvas"),
                tr("Há alterações não salvas. Deseja salvar antes de sair?"),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            )
            if ans == QMessageBox.StandardButton.Save:
                try:
                    self._save_current_vault()
                except Exception as e:
                    QMessageBox.critical(
                        self, tr("Falha ao salvar"),
                        tr("Não foi possível salvar: {error}. O aplicativo continuará aberto.", error=e),
                    )
                    event.ignore()
                    return
            elif ans == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        if self.vault_view:
            self.vault_view.clear_sensitive_clipboard()
        self.vault.lock()
        event.accept()

    def _shortcut_new_credential(self):
        if self.vault_view and self.vault.is_unlocked:
            self.vault_view._on_add_credential()

    def _shortcut_search(self):
        if self.vault_view and self.vault.is_unlocked:
            self.vault_view.search_input.setFocus()

    def _shortcut_copy_password(self):
        if self.vault_view and self.vault.is_unlocked:
            self.vault_view._copy_selected_password()

    def _request_safe_eject(self):
        QMessageBox.information(
            self,
            tr("Ejeção segura"),
            tr("Este dispositivo não oferece uma operação de ejeção segura compatível. Salve e bloqueie o cofre antes de remover a unidade."),
        )

    def _on_language_changed(self, language: str):
        set_language(language)
        self.ui_settings.setValue("interface/language", language)
        apply_translations(self, language)
        self.setWindowTitle(tr("Clavis — Cofre local de senhas"))

    def _save_current_vault(self):
        preserve_backup = (
            self.vault_view.settings_view.backup_enabled
            if self.vault_view is not None
            else True
        )
        return self.vault.save(preserve_backup=preserve_backup)

    @staticmethod
    def _apply_font_size(size: int):
        application = QApplication.instance()
        if application is not None:
            font = QFont(application.font())
            font.setPointSize(size)
            application.setFont(font)
