"""
Clavis Main Vault View (PySide6)
Credential list, search, filter, detail view, password history,
deleted items (trash) management, and atomic save controls.
"""

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QListView, QStackedWidget,
    QFrame, QMessageBox, QSizePolicy
)

from ..password_generator import analyze_password_health
from ..vault import ClavisVault
from .clipboard import ClipboardAutoClear
from .credential_dialog import CredentialDialog
from .icons import load_icon
from .settings_view import SettingsView


class VaultView(QWidget):
    """Primary authenticated vault workspace."""

    lock_requested = Signal()
    save_requested = Signal()

    def __init__(self, vault: ClavisVault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.current_selected_id: Optional[str] = None
        self.showing_deleted: bool = False
        self.grid_view_enabled = False
        self.clipboard_auto_clear = ClipboardAutoClear(self)
        self.clipboard_auto_clear.copied.connect(self._on_password_copied)
        self.clipboard_auto_clear.timer_finished.connect(self._on_clipboard_timer_finished)
        self._init_ui()
        self.refresh_list()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top Bar
        top_bar = QFrame()
        top_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        top_bar.setStyleSheet("background-color: #121316; border-bottom: 1px solid #2a2d39;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 8, 20, 8)

        logo = QLabel("CLAVIS")
        logo.setStyleSheet("color: #f3f4f6; font-size: 16px; font-weight: 800; letter-spacing: 1px;")
        top_layout.addWidget(logo)

        tagline = QLabel("OFFLINE SECURE VAULT")
        tagline.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 700; background-color: #064e3b; padding: 3px 8px; border-radius: 4px; margin-left: 8px;")
        top_layout.addWidget(tagline)

        top_layout.addStretch()

        self.save_status_label = QLabel("All changes saved")
        self.save_status_label.setStyleSheet("color: #9ca3af; font-size: 12px; margin-right: 12px;")
        top_layout.addWidget(self.save_status_label)

        self.save_btn = QPushButton("Save to USB")
        self.save_btn.setStyleSheet("background-color: #262933; color: #e5e7eb; border: 1px solid #374151; padding: 6px 14px; border-radius: 6px; font-weight: 500;")
        self.save_btn.clicked.connect(self._on_save)
        top_layout.addWidget(self.save_btn)

        self.lock_btn = QPushButton("Lock Vault")
        self.lock_btn.setStyleSheet("background-color: #991b1b; color: white; border: none; padding: 6px 14px; border-radius: 6px; font-weight: 600; margin-left: 8px;")
        self.lock_btn.clicked.connect(self.lock_requested.emit)
        top_layout.addWidget(self.lock_btn)

        main_layout.addWidget(top_bar)

        workspace = QHBoxLayout()
        workspace.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(190)
        sidebar.setStyleSheet(
            "background-color: #16181f; border-right: 1px solid #2a2d39;"
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(8)

        self.nav_all_btn = QPushButton("Credentials")
        self.nav_all_btn.setStyleSheet(self._nav_button_style(True))
        self.nav_all_btn.clicked.connect(self._show_credentials_tab)

        self.nav_trash_btn = QPushButton("Trash")
        self.nav_trash_btn.setStyleSheet(self._nav_button_style())
        self.nav_trash_btn.clicked.connect(self._show_trash_tab)

        self.nav_health_btn = QPushButton("Password Health")
        self.nav_health_btn.setStyleSheet(self._nav_button_style())
        self.nav_health_btn.clicked.connect(self._show_password_health)

        self.nav_settings_btn = QPushButton("Settings")
        self.nav_settings_btn.setStyleSheet(self._nav_button_style())
        self.nav_settings_btn.clicked.connect(self._show_settings_tab)

        for button in (
            self.nav_all_btn,
            self.nav_trash_btn,
            self.nav_health_btn,
            self.nav_settings_btn,
        ):
            button.setMinimumHeight(40)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            sidebar_layout.addWidget(button)
        sidebar_layout.addStretch()

        self.main_stack = QStackedWidget()
        self.main_stack.setStyleSheet("background-color: #1a1c23;")

        self.credentials_page = self._build_credentials_page()
        self.main_stack.addWidget(self.credentials_page)

        self.detail_widget = self._build_detail_widget()
        self.main_stack.addWidget(self.detail_widget)

        self.settings_view = SettingsView(self.vault)
        self.main_stack.addWidget(self.settings_view)

        self.password_health_view = self._build_password_health_widget()
        self.main_stack.addWidget(self.password_health_view)

        workspace.addWidget(sidebar)
        workspace.addWidget(self.main_stack, 1)
        main_layout.addLayout(workspace, 1)

    @staticmethod
    def _nav_button_style(active: bool = False) -> str:
        if active:
            return (
                "background-color: #4f46e5; color: white; border: none; "
                "padding: 10px 12px; border-radius: 6px; font-weight: 600; "
                "text-align: left;"
            )
        return (
            "background-color: transparent; color: #9ca3af; "
            "border: 1px solid transparent; padding: 10px 12px; "
            "border-radius: 6px; text-align: left;"
        )

    def _build_credentials_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #1a1c23;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        self.credentials_heading = QLabel("Credentials")
        self.credentials_heading.setStyleSheet(
            "color: #f9fafb; font-size: 22px; font-weight: 700;"
        )
        header_row.addWidget(self.credentials_heading)
        header_row.addStretch()

        self.add_btn = QPushButton("+ New")
        self.add_btn.setStyleSheet(
            "background-color: #4f46e5; color: white; border: none; "
            "border-radius: 6px; padding: 8px 12px; font-weight: 600;"
        )
        self.add_btn.clicked.connect(self._on_add_credential)
        header_row.addWidget(self.add_btn)

        self.view_mode_btn = QPushButton("Grid view")
        self.view_mode_btn.setStyleSheet(
            "background-color: #262933; color: #e5e7eb; border: 1px solid "
            "#374151; border-radius: 6px; padding: 8px 12px;"
        )
        self.view_mode_btn.setIcon(load_icon("gridview.svg"))
        self.view_mode_btn.setIconSize(QSize(18, 18))
        self.view_mode_btn.setCheckable(True)
        self.view_mode_btn.toggled.connect(self._toggle_credential_view)
        header_row.addWidget(self.view_mode_btn)
        layout.addLayout(header_row)

        # Search Bar
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search credentials (name, email, url)...")
        self.search_input.setStyleSheet("background-color: #121316; color: #f3f4f6; border: 1px solid #374151; border-radius: 6px; padding: 8px 10px;")
        self.search_input.textChanged.connect(self.refresh_list)
        search_row.addWidget(self.search_input, 1)

        self.empty_trash_btn = QPushButton("Empty Trash (Permanently Erase All)")
        self.empty_trash_btn.setStyleSheet(
            "background-color: #7f1d1d; color: #fca5a5; border: 1px solid "
            "#991b1b; padding: 8px; border-radius: 6px; font-weight: 600;"
        )
        self.empty_trash_btn.hide()
        self.empty_trash_btn.clicked.connect(self._on_empty_trash)
        search_row.addWidget(self.empty_trash_btn)
        layout.addLayout(search_row)

        self.cred_list = QListWidget()
        self.cred_list.setViewMode(QListView.ViewMode.ListMode)
        self.cred_list.setSpacing(6)
        self.cred_list.setUniformItemSizes(False)
        self.cred_list.setStyleSheet("""
            QListWidget {
                background-color: #121316;
                border: 1px solid #2a2d39;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                background-color: #1a1c23;
                color: #e5e7eb;
                border-radius: 4px;
                padding: 0;
            }
            QListWidget::item:selected {
                background-color: #2a2d3f;
                border: 1px solid #6366f1;
            }
            QListWidget::item:hover:!selected {
                background-color: #21242d;
            }
        """)
        self.cred_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.cred_list, 1)

        self.credential_empty_label = QLabel()
        self.credential_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.credential_empty_label.setStyleSheet(
            "color: #6b7280; font-size: 14px; padding: 24px;"
        )
        self.credential_empty_label.hide()
        layout.addWidget(self.credential_empty_label, 1)
        return page

    def _build_detail_widget(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background-color: #1a1c23;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        self.detail_container = QWidget()
        self.detail_container.setMaximumWidth(1080)
        dc_layout = QVBoxLayout(self.detail_container)
        dc_layout.setContentsMargins(0, 0, 0, 0)
        dc_layout.setSpacing(10)

        # Header with Title and Actions
        head_row = QHBoxLayout()
        self.back_to_list_btn = QPushButton("← Back to list")
        self.back_to_list_btn.setStyleSheet(self._nav_button_style())
        self.back_to_list_btn.clicked.connect(self._show_current_list)
        head_row.addWidget(self.back_to_list_btn)

        self.detail_title = QLabel("Service Title")
        self.detail_title.setStyleSheet("color: #f9fafb; font-size: 19px; font-weight: 700;")
        head_row.addWidget(self.detail_title)
        head_row.addStretch()

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setIcon(load_icon("edit.svg"))
        self.edit_btn.setIconSize(QSize(18, 18))
        self.edit_btn.setStyleSheet("background-color: #262933; color: #e5e7eb; border: 1px solid #374151; padding: 6px 14px; border-radius: 6px;")
        self.edit_btn.clicked.connect(self._on_edit_credential)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setIcon(load_icon("delete.svg"))
        self.delete_btn.setIconSize(QSize(18, 18))
        self.delete_btn.setStyleSheet("background-color: #7f1d1d; color: #fca5a5; border: 1px solid #991b1b; padding: 6px 14px; border-radius: 6px;")
        self.delete_btn.clicked.connect(self._on_delete_credential)

        self.restore_btn = QPushButton("Restore")
        self.restore_btn.setStyleSheet("background-color: #064e3b; color: #34d399; border: 1px solid #059669; padding: 6px 14px; border-radius: 6px;")
        self.restore_btn.clicked.connect(self._on_restore_credential)
        self.restore_btn.hide()

        head_row.addWidget(self.edit_btn)
        head_row.addWidget(self.delete_btn)
        head_row.addWidget(self.restore_btn)
        dc_layout.addLayout(head_row)

        # Fields Card
        fields_card = QFrame()
        fields_card.setStyleSheet("background-color: #121316; border: 1px solid #2a2d39; border-radius: 8px; padding: 10px;")
        fc_layout = QVBoxLayout(fields_card)
        fc_layout.setSpacing(7)

        # Username Row
        u_label = QLabel("USERNAME / EMAIL")
        u_label.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600;")
        fc_layout.addWidget(u_label)

        u_row = QHBoxLayout()
        self.detail_username = QLabel("")
        self.detail_username.setStyleSheet("color: #f3f4f6; font-size: 13px; font-weight: 500;")
        copy_u_btn = QPushButton("Copy")
        copy_u_btn.setStyleSheet("background-color: #262933; color: #9ca3af; border: 1px solid #374151; padding: 4px 10px; border-radius: 4px;")
        copy_u_btn.clicked.connect(self._copy_username)

        u_row.addWidget(self.detail_username, 1)
        u_row.addWidget(copy_u_btn)
        fc_layout.addLayout(u_row)

        # Password Row
        p_label = QLabel("PASSWORD")
        p_label.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600; margin-top: 8px;")
        fc_layout.addWidget(p_label)

        p_row = QHBoxLayout()
        self.detail_password = QLabel("••••••••••••••••")
        self.detail_password.setStyleSheet("color: #f3f4f6; font-size: 14px; font-family: monospace;")
        self._raw_password = ""
        self._pw_revealed = False

        self.toggle_reveal_btn = QPushButton("Reveal")
        self.toggle_reveal_btn.setIcon(load_icon("reveal_on.svg"))
        self.toggle_reveal_btn.setIconSize(QSize(18, 18))
        self.toggle_reveal_btn.setStyleSheet("background-color: #262933; color: #9ca3af; border: 1px solid #374151; padding: 4px 10px; border-radius: 4px;")
        self.toggle_reveal_btn.clicked.connect(self._toggle_password_reveal)

        self.copy_password_btn = QPushButton("Copy")
        self.copy_password_btn.setStyleSheet("background-color: #4f46e5; color: white; border: none; padding: 4px 12px; border-radius: 4px; font-weight: 600;")
        self.copy_password_btn.clicked.connect(self._copy_password)

        p_row.addWidget(self.detail_password, 1)
        p_row.addWidget(self.toggle_reveal_btn)
        p_row.addWidget(self.copy_password_btn)
        fc_layout.addLayout(p_row)

        # URL Row
        self.url_label = QLabel("WEBSITE")
        self.url_label.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600; margin-top: 8px;")
        fc_layout.addWidget(self.url_label)
        self.detail_url = QLabel("")
        self.detail_url.setStyleSheet("color: #60a5fa; font-size: 12px;")
        fc_layout.addWidget(self.detail_url)

        # Notes Row
        self.notes_label = QLabel("NOTES")
        self.notes_label.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600; margin-top: 8px;")
        fc_layout.addWidget(self.notes_label)
        self.detail_notes = QLabel("")
        self.detail_notes.setWordWrap(True)
        self.detail_notes.setStyleSheet("color: #d1d5db; font-size: 12px; background-color: #1a1c23; padding: 6px; border-radius: 6px; border: 1px solid #2a2d39;")
        fc_layout.addWidget(self.detail_notes)

        dc_layout.addWidget(fields_card)

        # Password History Section
        self.history_frame = QFrame()
        self.history_frame.setStyleSheet("background-color: #121316; border: 1px solid #2a2d39; border-radius: 8px; padding: 8px;")
        hf_layout = QVBoxLayout(self.history_frame)
        hf_title = QLabel("PASSWORD HISTORY")
        hf_title.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600;")
        hf_layout.addWidget(hf_title)

        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(72)
        self.history_list.setStyleSheet("background-color: #1a1c23; border: 1px solid #2a2d39; border-radius: 4px; color: #9ca3af; font-family: monospace;")
        hf_layout.addWidget(self.history_list)
        dc_layout.addWidget(self.history_frame)

        dc_layout.addStretch()
        layout.addWidget(
            self.detail_container,
            0,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        )

        return widget

    def _build_password_health_widget(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background-color: #1a1c23;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)

        title = QLabel("Password Health")
        title.setStyleSheet("color: #f9fafb; font-size: 22px; font-weight: 700;")
        layout.addWidget(title)

        description = QLabel(
            "Checks active credentials for weak or reused passwords. "
            "Analysis happens locally and does not check breach databases."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(description)

        self.health_scan_btn = QPushButton("Scan Vault")
        self.health_scan_btn.setStyleSheet("background-color: #4f46e5; color: white; border: none; padding: 8px 14px; border-radius: 6px; font-weight: 600;")
        self.health_scan_btn.clicked.connect(self._run_password_health_check)
        layout.addWidget(self.health_scan_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self.health_summary_label = QLabel("Run a scan to review your vault.")
        self.health_summary_label.setStyleSheet("color: #d1d5db; font-size: 14px; font-weight: 600;")
        layout.addWidget(self.health_summary_label)

        self.health_results = QListWidget()
        self.health_results.setStyleSheet(
            "background-color: #121316; border: 1px solid #2a2d39; "
            "border-radius: 6px; color: #e5e7eb; padding: 4px;"
        )
        self.health_results.itemClicked.connect(self._open_health_finding)
        layout.addWidget(self.health_results)
        return widget

    def refresh_list(self):
        if not self.vault.db:
            return

        self.cred_list.clear()
        query = self.search_input.text()
        creds = self.vault.db.list_credentials(
            include_deleted=self.showing_deleted,
            search_query=query
        )

        for c in creds:
            item = QListWidgetItem()
            item.setText(f"{c['title']}\n{c['username']}")
            item.setData(Qt.ItemDataRole.UserRole, c["id"])
            item.setSizeHint(
                QSize(260, 142) if self.grid_view_enabled else QSize(700, 76)
            )
            self.cred_list.addItem(item)
            self.cred_list.setItemWidget(
                item,
                self._build_credential_item_widget(c),
            )

        has_credentials = bool(creds)
        self.cred_list.setVisible(has_credentials)
        self.credential_empty_label.setVisible(not has_credentials)
        if not has_credentials:
            if query:
                message = "No credentials match your search."
            elif self.showing_deleted:
                message = "Trash is empty."
            else:
                message = "No credentials yet. Click + New to create one."
            self.credential_empty_label.setText(message)

    def _build_credential_item_widget(self, credential: dict) -> QWidget:
        is_deleted = bool(credential.get("is_deleted"))
        card = QFrame()
        card.setStyleSheet(
            "QFrame#credentialCard { background-color: #1a1c23; "
            "border: 1px solid #2a2d39; border-radius: 6px; }"
            "QLabel { color: #e5e7eb; background: transparent; border: none; }"
        )
        card.setObjectName("credentialCard")
        card.setProperty("credentialId", credential["id"])

        if self.grid_view_enabled:
            layout = QVBoxLayout(card)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(6)
        else:
            layout = QHBoxLayout(card)
            layout.setContentsMargins(12, 6, 8, 6)
            layout.setSpacing(8)

        identity = QWidget(card)
        identity_layout = QVBoxLayout(identity)
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(3)

        title = QLabel(credential["title"])
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        username = QLabel(credential["username"])
        username.setStyleSheet("color: #9ca3af; font-size: 12px;")
        username.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        identity_layout.addWidget(title)
        identity_layout.addWidget(username)
        layout.addWidget(identity, 1)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        view_button = QPushButton("View")
        view_button.setToolTip("View credential details")
        view_button.clicked.connect(
            lambda checked=False, cred_id=credential["id"]:
                self._view_credential(cred_id)
        )
        actions.addWidget(view_button)

        if not is_deleted:
            edit_button = QPushButton("Edit")
            edit_button.setIcon(load_icon("edit.svg"))
            edit_button.setIconSize(QSize(16, 16))
            edit_button.setToolTip("Edit credential")
            edit_button.clicked.connect(
                lambda checked=False, cred_id=credential["id"]:
                    self._edit_credential_by_id(cred_id)
            )
            actions.addWidget(edit_button)

        delete_button = QPushButton("Delete")
        delete_button.setIcon(load_icon("delete.svg"))
        delete_button.setIconSize(QSize(16, 16))
        delete_button.setToolTip(
            "Permanently delete credential" if is_deleted else "Move credential to Trash"
        )
        delete_button.clicked.connect(
            lambda checked=False, cred_id=credential["id"]:
                self._delete_credential_by_id(cred_id)
        )
        actions.addWidget(delete_button)
        if self.grid_view_enabled:
            layout.addStretch()
            layout.addLayout(actions)
        else:
            layout.addLayout(actions)

        card.setStyleSheet(card.styleSheet() + """
            QPushButton {
                background-color: #262933;
                color: #e5e7eb;
                border: 1px solid #374151;
                border-radius: 4px;
                padding: 5px 9px;
            }
            QPushButton:hover { background-color: #343846; }
        """)
        return card

    def _toggle_credential_view(self, enabled: bool):
        self.grid_view_enabled = enabled
        self.view_mode_btn.setText("List view" if enabled else "Grid view")
        self.view_mode_btn.setIcon(
            load_icon("rowview.svg" if enabled else "gridview.svg")
        )
        if enabled:
            self.cred_list.setViewMode(QListView.ViewMode.IconMode)
            self.cred_list.setFlow(QListView.Flow.LeftToRight)
            self.cred_list.setWrapping(True)
            self.cred_list.setResizeMode(QListView.ResizeMode.Adjust)
            self.cred_list.setGridSize(QSize(280, 142))
        else:
            self.cred_list.setViewMode(QListView.ViewMode.ListMode)
            self.cred_list.setFlow(QListView.Flow.TopToBottom)
            self.cred_list.setWrapping(False)
            self.cred_list.setResizeMode(QListView.ResizeMode.Fixed)
            self.cred_list.setGridSize(QSize())
        self.refresh_list()

    def _view_credential(self, credential_id: str):
        self._load_credential_detail(credential_id)

    def _edit_credential_by_id(self, credential_id: str):
        self.current_selected_id = credential_id
        self._on_edit_credential()

    def _delete_credential_by_id(self, credential_id: str):
        self.current_selected_id = credential_id
        self._on_delete_credential()

    def _on_item_clicked(self, item: QListWidgetItem):
        cred_id = item.data(Qt.ItemDataRole.UserRole)
        self._load_credential_detail(cred_id)

    def _load_credential_detail(self, cred_id: str):
        if not self.vault.db:
            return

        cred = self.vault.db.get_credential(cred_id)
        if not cred:
            return
        self.current_selected_id = cred_id
        self.main_stack.setCurrentWidget(self.detail_widget)

        self.detail_title.setText(cred["title"])
        self.detail_username.setText(cred["username"])
        self._raw_password = cred["password"]
        self._pw_revealed = False
        self.detail_password.setText("••••••••••••••••")
        self.toggle_reveal_btn.setText("Reveal")
        self.toggle_reveal_btn.setIcon(load_icon("reveal_on.svg"))
        self.copy_password_btn.setText("Copy")

        self.detail_url.setText(cred.get("url") or "None")
        self.detail_notes.setText(cred.get("notes") or "No notes recorded.")

        # Update buttons according to deleted state
        if cred.get("is_deleted"):
            self.edit_btn.hide()
            self.delete_btn.setText("Permanently Erase")
            self.restore_btn.show()
        else:
            self.edit_btn.show()
            self.delete_btn.setText("Delete")
            self.restore_btn.hide()

        # Load history
        self.history_list.clear()
        hist = self.vault.db.get_password_history(cred_id)
        if hist:
            self.history_frame.show()
            for h in hist:
                import datetime
                dt = datetime.datetime.fromtimestamp(h["changed_at"]).strftime("%Y-%m-%d %H:%M")
                self.history_list.addItem(f"{dt}: {h['old_password'][:2]}•••• (Previous)")
        else:
            self.history_frame.hide()

    def _toggle_password_reveal(self):
        if self._pw_revealed:
            self.detail_password.setText("••••••••••••••••")
            self.toggle_reveal_btn.setText("Reveal")
            self.toggle_reveal_btn.setIcon(load_icon("reveal_on.svg"))
            self._pw_revealed = False
        else:
            self.detail_password.setText(self._raw_password)
            self.toggle_reveal_btn.setText("Hide")
            self.toggle_reveal_btn.setIcon(load_icon("reveal_off.svg"))
            self._pw_revealed = True

    def _copy_password(self):
        self.clipboard_auto_clear.copy_password(self._raw_password)

    def _on_password_copied(self):
        self.copy_password_btn.setText("Copied (30s)")

    def _on_clipboard_timer_finished(self):
        self.copy_password_btn.setText("Copy")

    def clear_sensitive_clipboard(self):
        self.clipboard_auto_clear.clear_if_unchanged()

    def _copy_username(self):
        if self.detail_username.text():
            QGuiApplication.clipboard().setText(self.detail_username.text())

    def _on_add_credential(self):
        if not self.vault.db:
            return
        dlg = CredentialDialog(self, clipboard_auto_clear=self.clipboard_auto_clear)
        if dlg.exec():
            data = dlg.get_data()
            new_id = self.vault.db.add_credential(**data)
            self.vault.has_unsaved_changes = True
            self._update_save_status()
            self.refresh_list()
            self._load_credential_detail(new_id)

    def _on_edit_credential(self):
        if not self.current_selected_id or not self.vault.db:
            return
        cred = self.vault.db.get_credential(self.current_selected_id)
        if not cred:
            return

        dlg = CredentialDialog(
            self,
            existing_credential=cred,
            clipboard_auto_clear=self.clipboard_auto_clear,
        )
        if dlg.exec():
            data = dlg.get_data()
            self.vault.db.update_credential(self.current_selected_id, **data)
            self.vault.has_unsaved_changes = True
            self._update_save_status()
            self.refresh_list()
            self._load_credential_detail(self.current_selected_id)

    def _on_delete_credential(self):
        if not self.current_selected_id or not self.vault.db:
            return

        cred = self.vault.db.get_credential(self.current_selected_id)
        if not cred:
            return

        if cred.get("is_deleted"):
            # Permanent delete
            ans = QMessageBox.question(
                self,
                "Confirm Permanent Deletion",
                f"Permanently remove '{cred['title']}'? This action cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ans == QMessageBox.StandardButton.Yes:
                self.vault.db.permanently_delete_credential(self.current_selected_id)
                self.vault.has_unsaved_changes = True
                self._update_save_status()
                self.current_selected_id = None
                self.main_stack.setCurrentWidget(self.credentials_page)
                self.refresh_list()
        else:
            # Soft delete
            self.vault.db.soft_delete_credential(self.current_selected_id)
            self.vault.has_unsaved_changes = True
            self._update_save_status()
            self.current_selected_id = None
            self.main_stack.setCurrentWidget(self.credentials_page)
            self.refresh_list()

    def _on_restore_credential(self):
        if not self.current_selected_id or not self.vault.db:
            return
        self.vault.db.restore_credential(self.current_selected_id)
        self.vault.has_unsaved_changes = True
        self._update_save_status()
        self.refresh_list()
        self._load_credential_detail(self.current_selected_id)

    def _on_empty_trash(self):
        if not self.vault.db:
            return
        ans = QMessageBox.question(
            self,
            "Empty Trash Confirmation",
            "Are you sure you want to permanently delete all items in Trash? "
            "Logical deletion cannot guarantee physical erasure from flash memory, "
            "but these entries will be purged from the encrypted vault.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.vault.db.empty_trash()
            self.vault.has_unsaved_changes = True
            self._update_save_status()
            self.refresh_list()

    def _on_save(self):
        self.save_requested.emit()

    def _update_save_status(self):
        if self.vault.has_unsaved_changes:
            self.save_status_label.setText("● Unsaved changes on USB")
            self.save_status_label.setStyleSheet("color: #f59e0b; font-size: 12px; margin-right: 12px; font-weight: 600;")
        else:
            self.save_status_label.setText("All changes saved")
            self.save_status_label.setStyleSheet("color: #34d399; font-size: 12px; margin-right: 12px;")

    def mark_saved(self):
        self._update_save_status()

    def _set_active_navigation(self, active_button: QPushButton) -> None:
        for button in (
            self.nav_all_btn,
            self.nav_trash_btn,
            self.nav_health_btn,
            self.nav_settings_btn,
        ):
            button.setStyleSheet(self._nav_button_style(button is active_button))

    def _show_current_list(self):
        if self.showing_deleted:
            self._show_trash_tab()
        else:
            self._show_credentials_tab()

    def _show_credentials_tab(self):
        self.showing_deleted = False
        self._set_active_navigation(self.nav_all_btn)
        self.credentials_heading.setText("Credentials")
        self.add_btn.show()
        self.empty_trash_btn.hide()
        self.main_stack.setCurrentWidget(self.credentials_page)
        self.refresh_list()

    def _show_trash_tab(self):
        self.showing_deleted = True
        self._set_active_navigation(self.nav_trash_btn)
        self.credentials_heading.setText("Trash")
        self.add_btn.hide()
        self.empty_trash_btn.show()
        self.main_stack.setCurrentWidget(self.credentials_page)
        self.refresh_list()

    def _show_settings_tab(self):
        self._set_active_navigation(self.nav_settings_btn)
        self.main_stack.setCurrentWidget(self.settings_view)

    def _show_password_health(self):
        self._set_active_navigation(self.nav_health_btn)
        self.main_stack.setCurrentWidget(self.password_health_view)
        self._run_password_health_check()

    def _run_password_health_check(self):
        if not self.vault.db:
            return

        credentials = self.vault.db.list_credentials(include_deleted=False)
        findings = analyze_password_health(credentials)
        self.health_results.clear()

        if not credentials:
            self.health_summary_label.setText("No active credentials to scan.")
            return
        if not findings:
            self.health_summary_label.setText(
                "No weak or reused passwords found in the active credentials."
            )
            return

        self.health_summary_label.setText(
            f"{len(findings)} credential(s) need attention. "
            "Select an item to open it."
        )
        for finding in findings:
            item = QListWidgetItem(
                f"{finding.title}\n" + " · ".join(finding.issues)
            )
            item.setData(Qt.ItemDataRole.UserRole, finding.credential_id)
            self.health_results.addItem(item)

    def _open_health_finding(self, item: QListWidgetItem):
        cred_id = item.data(Qt.ItemDataRole.UserRole)
        self.search_input.clear()
        self._show_credentials_tab()
        for index in range(self.cred_list.count()):
            credential_item = self.cred_list.item(index)
            if credential_item.data(Qt.ItemDataRole.UserRole) == cred_id:
                self.cred_list.setCurrentItem(credential_item)
                break
        self._load_credential_detail(cred_id)
