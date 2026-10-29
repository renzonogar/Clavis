"""
Clavis Main Vault View (PySide6)
Credential list, search, filter, detail view, password history,
deleted items (trash) management, and atomic save controls.
"""

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from PySide6.QtCore import QSize, Qt, Signal, QUrl, QTimer
from PySide6.QtGui import QGuiApplication, QPixmap, QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QListWidget, QListWidgetItem, QListView, QStackedWidget,
    QFrame, QMessageBox, QSizePolicy, QFileDialog, QInputDialog
)

from ..password_generator import analyze_password_health, PasswordGenerator
from .. import __version__
from ..storage import SafeVaultStorage
from ..vault import ClavisVault
from .clipboard import ClipboardAutoClear
from .credential_dialog import CredentialDialog
from .icons import load_icon
from .settings_view import SettingsView
from .utility_views import PasswordGeneratorView, VaultManagementView, AboutView
from .i18n import (
    apply_translations,
    set_translated_text,
    set_untranslated_text,
    tr,
)


class VaultView(QWidget):
    """Primary authenticated vault workspace."""

    lock_requested = Signal()
    save_requested = Signal()
    eject_requested = Signal()

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
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(260)
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet("#sidebar { background:#0e1113; border-right:1px solid #20262a; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(24, 24, 24, 20)
        sidebar_layout.setSpacing(8)

        logo_row = QHBoxLayout()
        logo_path = Path(__file__).resolve().parents[3] / "assets" / "favicon.png"
        logo = QLabel()
        logo_pixmap = QPixmap(str(logo_path))
        if not logo_pixmap.isNull():
            logo.setPixmap(logo_pixmap.scaled(
                34, 34, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        logo_row.addWidget(logo)
        brand = QLabel("CLAVIS")
        brand.setStyleSheet("color:#e8edf2; font-size:17px; font-weight:800;")
        logo_row.addWidget(brand)
        logo_row.addStretch()
        sidebar_layout.addLayout(logo_row)
        version = QLabel(f"v{__version__}")
        version.setStyleSheet("color:#5e6b76; font-size:10px; font-family:Consolas,monospace; margin-left:43px;")
        sidebar_layout.addWidget(version)
        sidebar_layout.addSpacing(22)

        self.nav_all_btn = QPushButton("Senhas")
        self.nav_all_btn.setIcon(load_icon("credential.svg"))
        self.nav_all_btn.setStyleSheet(self._nav_button_style(True))
        self.nav_all_btn.clicked.connect(self._show_credentials_tab)

        self.nav_trash_btn = QPushButton("Lixeira")
        self.nav_trash_btn.setIcon(load_icon("delete.svg"))
        self.nav_trash_btn.setStyleSheet(self._nav_button_style())
        self.nav_trash_btn.clicked.connect(self._show_trash_tab)

        self.nav_health_btn = QPushButton("Saúde")
        self.nav_health_btn.setIcon(load_icon("health.svg"))
        self.nav_health_btn.setStyleSheet(self._nav_button_style())
        self.nav_health_btn.clicked.connect(self._show_password_health)

        self.nav_generator_btn = QPushButton("Gerar")
        self.nav_generator_btn.setIcon(load_icon("generate.svg"))
        self.nav_generator_btn.setStyleSheet(self._nav_button_style())
        self.nav_generator_btn.clicked.connect(self._show_generator)

        self.nav_usb_btn = QPushButton("Cofre")
        self.nav_usb_btn.setIcon(load_icon("vault.svg"))
        self.nav_usb_btn.setStyleSheet(self._nav_button_style())
        self.nav_usb_btn.clicked.connect(self._show_usb)

        self.nav_settings_btn = QPushButton("Configurações")
        self.nav_settings_btn.setIcon(load_icon("settings.svg"))
        self.nav_settings_btn.setStyleSheet(self._nav_button_style())
        self.nav_settings_btn.clicked.connect(self._show_settings_tab)

        self.nav_about_btn = QPushButton("Sobre")
        self.nav_about_btn.setIcon(load_icon("info.svg"))
        self.nav_about_btn.setStyleSheet(self._nav_button_style())
        self.nav_about_btn.clicked.connect(self._show_about)

        self.nav_buttons = (
            self.nav_all_btn,
            self.nav_generator_btn,
            self.nav_health_btn,
            self.nav_usb_btn,
            self.nav_trash_btn,
            self.nav_settings_btn,
            self.nav_about_btn,
        )
        for button in (
            *self.nav_buttons,
        ):
            button.setMinimumHeight(42)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            button.setIconSize(QSize(18, 18))
            sidebar_layout.addWidget(button)
        sidebar_layout.addStretch()

        self.eject_btn = QPushButton("Ejetar Cofre")
        self.eject_btn.setIcon(load_icon("perma_delete.svg"))
        self.eject_btn.setIconSize(QSize(32, 32))
        self.eject_btn.setStyleSheet(
            "QPushButton { background:#211116; color:#ff4264; border:1px solid #702638; "
            "border-radius:5px; padding:10px 12px; font-weight:700; text-align:left; }"
            "QPushButton:hover { background:#32151e; }"
        )
        self.eject_btn.clicked.connect(self.eject_requested.emit)
        sidebar_layout.addWidget(self.eject_btn)
        self.exit_btn = QPushButton("Sair do Clavis")
        self.exit_btn.setIcon(load_icon("exit.svg"))
        self.exit_btn.setIconSize(QSize(16, 16))
        self.exit_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#73808a; border:0; "
            "padding:8px 12px; text-align:left; }"
            "QPushButton:hover { color:#e8edf2; }"
        )
        self.exit_btn.clicked.connect(lambda: self.window().close())
        sidebar_layout.addWidget(self.exit_btn)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 24, 32, 22)
        content_layout.setSpacing(18)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por serviço, usuário ou URL...")
        self.search_input.setMinimumHeight(40)
        self.search_input.setStyleSheet(
            "QLineEdit { background:#0e1113; color:#e8edf2; border:1px solid #252d32; "
            "border-radius:6px; padding:0 14px; selection-background-color:#284cff; }"
            "QLineEdit:focus { border-color:#284cff; }"
        )
        self.search_input.textChanged.connect(self.refresh_list)
        toolbar.addWidget(self.search_input, 1)

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Todos os itens", "all")
        self.filter_combo.addItem("Senhas fracas", "weak")
        self.filter_combo.addItem("Senhas reutilizadas", "reused")
        self.filter_combo.setMinimumHeight(40)
        self.filter_combo.setStyleSheet(
            "QComboBox { background:#08090a; color:#c8d0d7; border:1px solid #252d32; "
            "border-radius:6px; padding:0 12px; min-width:138px; }"
            "QComboBox::drop-down { border:0; width:24px; }"
            "QComboBox QAbstractItemView { background:#13171a; color:#e8edf2; "
            "selection-background-color:#17213d; border:1px solid #252d32; }"
        )
        self.filter_combo.currentIndexChanged.connect(self.refresh_list)
        toolbar.addWidget(self.filter_combo)

        self.credentials_heading = QLabel("SENHAS SALVAS")
        self.credentials_heading.setStyleSheet(
            "color:#596875; font-size:10px; font-weight:700; "
            "font-family:Consolas,monospace; padding:0 4px;"
        )
        toolbar.addWidget(self.credentials_heading)

        self.save_status_label = QLabel("Alterações salvas")
        self.save_status_label.setStyleSheet("color:#73808a; font-size:11px;")
        toolbar.addWidget(self.save_status_label)

        self.save_btn = QPushButton("Salvar")
        self.save_btn.setStyleSheet(
            "QPushButton { background:#13171a; color:#b9c3cc; border:1px solid #252d32; "
            "border-radius:5px; padding:9px 13px; }"
            "QPushButton:hover { border-color:#53616b; }"
        )
        self.save_btn.clicked.connect(self._on_save)
        toolbar.addWidget(self.save_btn)

        self.view_mode_btn = QPushButton()
        self.view_mode_btn.setStyleSheet(
            "QPushButton { background:#08090a; border:1px solid #252d32; "
            "border-radius:5px; padding:8px; }"
            "QPushButton:hover { border-color:#284cff; }"
        )
        self.view_mode_btn.setIcon(load_icon("gridview.svg"))
        self.view_mode_btn.setIconSize(QSize(19, 19))
        self.view_mode_btn.setCheckable(True)
        self.view_mode_btn.setToolTip("Alternar entre lista e grade")
        self.view_mode_btn.toggled.connect(self._toggle_credential_view)
        toolbar.addWidget(self.view_mode_btn)

        self.add_btn = QPushButton("Nova senha")
        self.add_btn.setIcon(load_icon("add.svg"))
        self.add_btn.setIconSize(QSize(17, 17))
        self.add_btn.setMinimumHeight(40)
        self.add_btn.setStyleSheet(
            "QPushButton { background:#f0f3f7; color:#08090a; border:0; "
            "border-radius:5px; padding:0 16px; font-weight:700; }"
            "QPushButton:hover { background:#dbe3ec; }"
        )
        self.add_btn.clicked.connect(self._on_add_credential)
        toolbar.addWidget(self.add_btn)
        content_layout.addLayout(toolbar)

        self.security_notice = QLabel(
            "Aviso de segurança: enquanto o cofre está desbloqueado, dados podem residir na memória. "
            "O sistema operacional pode usar paginação ou gerar dumps."
        )
        self.security_notice.setWordWrap(True)
        self.security_notice.setStyleSheet(
            "QLabel { background:#13171a; color:#aeb8c1; border-left:3px solid #d6dde5; "
            "padding:12px 15px; font-size:11px; }"
        )
        content_layout.addWidget(self.security_notice)

        self.main_stack = QStackedWidget()
        self.main_stack.setStyleSheet("background-color: #08090a;")

        self.credentials_page = self._build_credentials_page()
        self.main_stack.addWidget(self.credentials_page)

        self.detail_widget = self._build_detail_widget()
        self.main_stack.addWidget(self.detail_widget)

        self.settings_view = SettingsView(self.vault)
        self.main_stack.addWidget(self.settings_view)

        self.password_health_view = self._build_password_health_widget()
        self.main_stack.addWidget(self.password_health_view)
        self.generator_view = PasswordGeneratorView(self.clipboard_auto_clear)
        self.generator_view.save_requested.connect(self._save_generated_password)
        self.main_stack.addWidget(self.generator_view)
        self.usb_view = VaultManagementView(self.vault)
        self.usb_view.import_requested.connect(self._import_vault)
        self.usb_view.export_requested.connect(self._export_vault)
        self.main_stack.addWidget(self.usb_view)
        self.about_view = AboutView()
        self.main_stack.addWidget(self.about_view)

        content_layout.addWidget(self.main_stack, 1)
        main_layout.addWidget(sidebar)
        main_layout.addWidget(content, 1)
        apply_translations(self)

    @staticmethod
    def _nav_button_style(active: bool = False) -> str:
        if active:
            return (
                "QPushButton { background:#10182b; color:#e7edf5; border:0; "
                "border-left:2px solid #284cff; padding:10px 12px; border-radius:5px; "
                "font-weight:600; text-align:left; }"
            )
        return (
            "QPushButton { background:transparent; color:#91a0ad; border:0; "
            "border-left:2px solid transparent; padding:10px 12px; "
            "border-radius:5px; text-align:left; }"
            "QPushButton:hover { background:#13171a; color:#e7edf5; }"
        )

    def _build_credentials_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #08090a;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        self.empty_trash_btn = QPushButton("Esvaziar lixeira permanentemente")
        self.empty_trash_btn.setStyleSheet(
            "QPushButton { background:#211116; color:#ff4264; border:1px solid #702638; "
            "padding:9px 12px; border-radius:5px; font-weight:700; }"
            "QPushButton:hover { background:#32151e; }"
        )
        self.empty_trash_btn.hide()
        self.empty_trash_btn.clicked.connect(self._on_empty_trash)
        layout.addWidget(self.empty_trash_btn, 0, Qt.AlignmentFlag.AlignRight)

        columns = QHBoxLayout()
        columns.setContentsMargins(16, 0, 12, 0)
        columns.setSpacing(12)
        for text, stretch in (
            ("SERVIÇO & URL", 3), ("LOGIN / USUÁRIO", 2),
            ("SENHA", 2), ("SEGURANÇA", 1), ("AÇÕES", 2),
        ):
            label = QLabel(text)
            label.setStyleSheet(
                "color:#596875; font-size:9px; font-weight:700; "
                "font-family:Consolas,monospace;"
            )
            columns.addWidget(label, stretch)
        layout.addLayout(columns)

        self.cred_list = QListWidget()
        self.cred_list.setViewMode(QListView.ViewMode.ListMode)
        self.cred_list.setMovement(QListView.Movement.Static)
        self.cred_list.setDragEnabled(False)
        self.cred_list.setAcceptDrops(False)
        self.cred_list.setDragDropMode(QListView.DragDropMode.NoDragDrop)
        self.cred_list.setSpacing(6)
        self.cred_list.setUniformItemSizes(False)
        self.cred_list.setStyleSheet("""
            QListWidget {
                background:transparent;
                border:0;
                padding:0;
            }
            QListWidget::item {
                background-color: #0b0d0f;
                border:1px solid #20262a;
                color: #e5e7eb;
                border-radius: 7px;
                padding: 0;
            }
            QListWidget::item:selected {
                background-color: #101623;
                border: 1px solid #284cff;
            }
            QListWidget::item:hover:!selected {
                background-color: #111518;
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
        widget.setStyleSheet("background-color: #08090a;")
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
        self.back_to_list_btn = QPushButton("← Voltar à lista")
        self.back_to_list_btn.setStyleSheet(self._nav_button_style())
        self.back_to_list_btn.clicked.connect(self._show_current_list)
        head_row.addWidget(self.back_to_list_btn)

        self.detail_title = QLabel("Serviço")
        self.detail_title.setStyleSheet("color: #f9fafb; font-size: 19px; font-weight: 700;")
        head_row.addWidget(self.detail_title)
        head_row.addStretch()

        self.edit_btn = QPushButton("Editar")
        self.edit_btn.setIcon(load_icon("edit.svg"))
        self.edit_btn.setIconSize(QSize(18, 18))
        self.edit_btn.setStyleSheet("background-color: #262933; color: #e5e7eb; border: 1px solid #374151; padding: 6px 14px; border-radius: 6px;")
        self.edit_btn.clicked.connect(self._on_edit_credential)

        self.delete_btn = QPushButton("")
        self.delete_btn.setIcon(load_icon("delete.svg"))
        self.delete_btn.setIconSize(QSize(18, 18))
        self.delete_btn.setStyleSheet("background-color: #7f1d1d; color: #fca5a5; border: 1px solid #991b1b; padding: 6px 14px; border-radius: 6px;")
        self.delete_btn.clicked.connect(self._on_delete_credential)

        self.restore_btn = QPushButton("Restaurar")
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
        u_label = QLabel("USUÁRIO / E-MAIL")
        u_label.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600;")
        fc_layout.addWidget(u_label)

        u_row = QHBoxLayout()
        self.detail_username = QLabel("")
        self.detail_username.setStyleSheet("color: #f3f4f6; font-size: 13px; font-weight: 500;")
        copy_u_btn = QPushButton("Copiar")
        copy_u_btn.setStyleSheet("background-color: #262933; color: #9ca3af; border: 1px solid #374151; padding: 4px 10px; border-radius: 4px;")
        copy_u_btn.clicked.connect(self._copy_username)

        u_row.addWidget(self.detail_username, 1)
        u_row.addWidget(copy_u_btn)
        fc_layout.addLayout(u_row)

        # Password Row
        p_label = QLabel("SENHA")
        p_label.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600; margin-top: 8px;")
        fc_layout.addWidget(p_label)

        p_row = QHBoxLayout()
        self.detail_password = QLabel("••••••••••••••••")
        self.detail_password.setStyleSheet("color: #f3f4f6; font-size: 14px; font-family: monospace;")
        self._raw_password = ""
        self._pw_revealed = False
        self._reveal_timer = QTimer(self)
        self._reveal_timer.setSingleShot(True)
        self._reveal_timer.setInterval(10_000)
        self._reveal_timer.timeout.connect(self._hide_password)

        self.toggle_reveal_btn = QPushButton("Mostrar")
        self.toggle_reveal_btn.setIcon(load_icon("reveal_on.svg"))
        self.toggle_reveal_btn.setIconSize(QSize(18, 18))
        self.toggle_reveal_btn.setStyleSheet("background-color: #262933; color: #9ca3af; border: 1px solid #374151; padding: 4px 10px; border-radius: 4px;")
        self.toggle_reveal_btn.clicked.connect(self._toggle_password_reveal)

        self.copy_password_btn = QPushButton("Copiar")
        self.copy_password_btn.setStyleSheet("background-color: #4f46e5; color: white; border: none; padding: 4px 12px; border-radius: 4px; font-weight: 600;")
        self.copy_password_btn.clicked.connect(self._copy_password)

        p_row.addWidget(self.detail_password, 1)
        p_row.addWidget(self.toggle_reveal_btn)
        p_row.addWidget(self.copy_password_btn)
        fc_layout.addLayout(p_row)

        self.url_label = QLabel("SITE")
        self.url_label.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600; margin-top: 8px;")
        fc_layout.addWidget(self.url_label)
        self.detail_url = QLabel("")
        self.detail_url.setStyleSheet("color: #60a5fa; font-size: 12px;")
        url_row = QHBoxLayout()
        url_row.addWidget(self.detail_url, 1)
        self.open_url_btn = QPushButton("Abrir site")
        self.open_url_btn.clicked.connect(self._open_credential_url)
        url_row.addWidget(self.open_url_btn)
        fc_layout.addLayout(url_row)

        # Notes Row
        self.notes_label = QLabel("ANOTAÇÕES")
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
        hf_title = QLabel("HISTÓRICO DE SENHAS")
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

        title = QLabel("Saúde das senhas")
        title.setStyleSheet("color: #f9fafb; font-size: 22px; font-weight: 700;")
        layout.addWidget(title)

        description = QLabel(
            "Identifica senhas fracas ou reutilizadas. A análise acontece localmente "
            "e não consulta bases de vazamentos."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(description)

        self.health_scan_btn = QPushButton("Analisar cofre")
        self.health_scan_btn.setStyleSheet("background-color: #284cff; color: white; border: none; padding: 8px 14px; border-radius: 6px; font-weight: 600;")
        self.health_scan_btn.clicked.connect(self._run_password_health_check)
        layout.addWidget(self.health_scan_btn, 0, Qt.AlignmentFlag.AlignLeft)

        metrics = QHBoxLayout()
        total_card, self.health_total_value = self._health_metric("TOTAL", "—", "#284cff")
        weak_card, self.health_weak_value = self._health_metric("FRACAS", "—", "#ef4444")
        reused_card, self.health_reused_value = self._health_metric("REUTILIZADAS", "—", "#f59e0b")
        for metric in (total_card, weak_card, reused_card):
            metrics.addWidget(metric, 1)
        layout.addLayout(metrics)

        self.health_summary_label = QLabel("Execute uma análise para revisar o cofre.")
        self.health_summary_label.setStyleSheet("color: #d1d5db; font-size: 14px; font-weight: 600;")
        layout.addWidget(self.health_summary_label)

        self.health_results = QListWidget()
        self.health_results.setStyleSheet(
            "background-color: #0e1113; border: 1px solid #252a2d; "
            "border-radius: 6px; color: #e5e7eb; padding: 4px;"
        )
        self.health_results.itemClicked.connect(self._open_health_finding)
        layout.addWidget(self.health_results)
        return widget

    @staticmethod
    def _health_metric(title: str, value: str, accent: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: #0e1113; border: 1px solid #252a2d; "
            f"border-top: 2px solid {accent}; border-radius: 6px; }}"
        )
        content = QVBoxLayout(card)
        content.setContentsMargins(12, 9, 12, 9)
        name = QLabel(title)
        name.setStyleSheet("color: #9da5aa; font-size: 10px; font-weight: 700;")
        count = QLabel(value)
        count.setStyleSheet(f"color: {accent}; font-size: 22px; font-weight: 700;")
        content.addWidget(name)
        content.addWidget(count)
        return card, count

    def refresh_list(self):
        if not self.vault.db:
            return

        self.cred_list.clear()
        query = self.search_input.text()
        creds = self.vault.db.list_credentials(
            include_deleted=self.showing_deleted,
            search_query=query
        )
        self.filter_combo.setVisible(not self.showing_deleted)
        filter_kind = self.filter_combo.currentData()
        if filter_kind in ("weak", "reused") and not self.showing_deleted:
            findings = analyze_password_health(creds)
            creds_by_id = {credential["id"]: credential for credential in creds}
            finding_ids = {
                finding.credential_id for finding in findings
                if filter_kind == "weak" and any(
                    issue.startswith(("Weak password", "Could be stronger"))
                    for issue in finding.issues
                )
                or filter_kind == "reused" and "Reused password" in finding.issues
            }
            creds = [
                credential for credential_id, credential in creds_by_id.items()
                if credential_id in finding_ids
            ]

        for c in creds:
            item = QListWidgetItem()
            item.setText(f"{c['title']}\n{c['username']}")
            item.setData(Qt.ItemDataRole.UserRole, c["id"])
            item.setSizeHint(QSize(260, 142) if self.grid_view_enabled else QSize(900, 72))
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
                message = tr("Nenhuma credencial corresponde à busca.")
            elif filter_kind != "all" and not self.showing_deleted:
                message = tr("Nenhuma senha corresponde a este filtro.")
            elif self.showing_deleted:
                message = tr("A lixeira está vazia.")
            else:
                message = tr("Nenhuma credencial ainda. Use + para criar uma.")
            set_translated_text(self.credential_empty_label, message)
        apply_translations(self)

    def _build_credential_item_widget(self, credential: dict) -> QWidget:
        is_deleted = bool(credential.get("is_deleted"))
        card = QFrame()
        card.setStyleSheet(
            "QFrame#credentialCard { background:#0b0d0f; "
            "border:1px solid #20262a; border-radius:7px; }"
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

        title = QLabel()
        set_untranslated_text(title, credential["title"])
        title.setStyleSheet("font-size:13px; font-weight:650;")
        title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        url = QLabel()
        if credential.get("url"):
            set_untranslated_text(url, credential["url"])
        else:
            url.setText(tr("Sem URL"))
        url.setStyleSheet("color:#64717a; font-size:10px; font-family:Consolas,monospace;")
        url.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        username = QLabel()
        set_untranslated_text(username, credential["username"] or "—")
        username.setStyleSheet("color:#d7dde2; font-size:11px; font-family:Consolas,monospace;")
        username.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        identity_layout.addWidget(title)
        identity_layout.addWidget(url)
        if self.grid_view_enabled:
            identity_layout.addWidget(username)
            layout.addWidget(identity, 1)
        else:
            layout.addWidget(identity, 3)
            layout.addWidget(username, 2)

        password_box = QWidget()
        password_row = QHBoxLayout(password_box)
        password_row.setContentsMargins(0, 0, 0, 0)
        password_row.setSpacing(4)
        masked_password = QLabel("••••••••••••••")
        masked_password.setStyleSheet(
            "color:#dce2e7; font-size:11px; font-family:Consolas,monospace;"
        )
        masked_password.setToolTip("Senha oculta")
        password_row.addWidget(masked_password)
        reveal_button = QPushButton()
        reveal_button.setIcon(load_icon("reveal_on.svg"))
        reveal_button.setIconSize(QSize(14, 14))
        reveal_button.setFixedSize(24, 24)
        reveal_button.setCheckable(True)
        reveal_button.setToolTip("Revelar senha por 10 segundos")
        reveal_button.setStyleSheet("QPushButton { background:transparent; border:0; padding:2px; }")
        reveal_timer = QTimer(reveal_button)
        reveal_timer.setSingleShot(True)
        reveal_timer.setInterval(10_000)

        def set_row_reveal(visible: bool):
            masked_password.setText(
                credential.get("password", "") if visible else "••••••••••••••"
            )
            reveal_button.setIcon(
                load_icon("reveal_off.svg" if visible else "reveal_on.svg")
            )
            if visible:
                reveal_timer.start()
            else:
                reveal_timer.stop()

        reveal_button.toggled.connect(set_row_reveal)
        reveal_timer.timeout.connect(lambda: reveal_button.setChecked(False))
        password_row.addWidget(reveal_button)
        if self.grid_view_enabled:
            layout.addWidget(password_box)
        else:
            layout.addWidget(password_box, 2)

        strength = PasswordGenerator.estimate_strength(credential.get("password", ""))
        strength_colors = ("#ef4444", "#ef4444", "#f59e0b", "#22c55e", "#22c55e")
        strength_labels = ("Muito fraca", "Fraca", "Razoável", "Forte", "Muito forte")
        score = max(0, min(4, int(strength["score"])))
        strength_widget = QWidget()
        strength_layout = QVBoxLayout(strength_widget)
        strength_layout.setContentsMargins(0, 0, 0, 0)
        strength_layout.setSpacing(4)
        strength_label = QLabel(tr(strength_labels[score]))
        strength_label.setStyleSheet(
            f"color:{strength_colors[score]}; font-size:10px; font-weight:700;"
        )
        if self.grid_view_enabled:
            strength_layout.addWidget(strength_label)
        else:
            bars = QWidget()
            bars_layout = QHBoxLayout(bars)
            bars_layout.setContentsMargins(0, 0, 0, 0)
            bars_layout.setSpacing(3)
            for bar_index in range(4):
                bar = QFrame()
                bar.setFixedSize(12, 3)
                bar.setStyleSheet(
                    f"background:{strength_colors[score] if bar_index < score else '#263039'}; border:0; border-radius:1px;"
                )
                bars_layout.addWidget(bar)
            strength_layout.addWidget(bars)
            strength_layout.addWidget(strength_label)
        layout.addWidget(strength_widget, 1 if not self.grid_view_enabled else 0)

        actions = QHBoxLayout()
        actions.setSpacing(4)
        view_button = QPushButton("")
        view_button.setIcon(load_icon("reveal_on.svg"))
        view_button.setIconSize(QSize(16, 16))
        view_button.setToolTip("Ver detalhes")
        view_button.clicked.connect(
            lambda checked=False, cred_id=credential["id"]:
                self._view_credential(cred_id)
        )
        actions.addWidget(view_button)

        copy_user_button = QPushButton("")
        copy_user_button.setIcon(load_icon("credent.svg"))
        copy_user_button.setIconSize(QSize(16, 16))
        copy_user_button.setToolTip("Copiar usuário")
        copy_user_button.clicked.connect(
            lambda checked=False, value=credential.get("username", ""):
                QGuiApplication.clipboard().setText(value)
        )
        actions.addWidget(copy_user_button)

        copy_password_button = QPushButton("")
        copy_password_button.setIcon(load_icon("copy.svg"))
        copy_password_button.setIconSize(QSize(16, 16))
        copy_password_button.setToolTip("Copiar senha")
        copy_password_button.clicked.connect(
            lambda checked=False, value=credential.get("password", ""):
                self.clipboard_auto_clear.copy_password(value)
        )
        actions.addWidget(copy_password_button)

        if not is_deleted:
            edit_button = QPushButton("")
            edit_button.setIcon(load_icon("edit.svg"))
            edit_button.setIconSize(QSize(16, 16))
            edit_button.setToolTip("Editar credencial")
            edit_button.clicked.connect(
                lambda checked=False, cred_id=credential["id"]:
                    self._edit_credential_by_id(cred_id)
            )
            actions.addWidget(edit_button)

        delete_button = QPushButton("")
        delete_button.setIcon(load_icon("delete.svg"))
        delete_button.setIconSize(QSize(16, 16))
        delete_button.setToolTip(
            "Excluir permanentemente" if is_deleted else "Mover para a lixeira"
        )
        delete_button.clicked.connect(
            lambda checked=False, cred_id=credential["id"]:
                self._delete_credential_by_id(cred_id)
        )
        actions.addWidget(delete_button)
        for button in (view_button, copy_user_button, copy_password_button, delete_button):
            button.setFixedSize(30, 30)
        if self.grid_view_enabled:
            layout.addStretch()
            layout.addLayout(actions)
        else:
            layout.addLayout(actions, 2)

        card.setStyleSheet(card.styleSheet() + """
            QPushButton {
                background:#0b0d0f;
                color:#94a1ac;
                border:1px solid #222a2f;
                border-radius:4px;
                padding:4px;
            }
            QPushButton:hover { background:#101623; border-color:#284cff; }
        """)
        return card

    def _toggle_credential_view(self, enabled: bool):
        self.grid_view_enabled = enabled
        self.view_mode_btn.setIcon(
            load_icon("rowview.svg" if enabled else "gridview.svg")
        )
        if enabled:
            self.cred_list.setViewMode(QListView.ViewMode.IconMode)
            self.cred_list.setMovement(QListView.Movement.Static)
            self.cred_list.setDragEnabled(False)
            self.cred_list.setAcceptDrops(False)
            self.cred_list.setDragDropMode(QListView.DragDropMode.NoDragDrop)
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
        self._set_list_toolbar_visible(False)
        self.main_stack.setCurrentWidget(self.detail_widget)

        set_untranslated_text(self.detail_title, cred["title"])
        set_untranslated_text(self.detail_username, cred["username"])
        self._raw_password = cred["password"]
        self._reveal_timer.stop()
        self._pw_revealed = False
        self.detail_password.setText("••••••••••••••••")
        self.toggle_reveal_btn.setIcon(load_icon("reveal_on.svg"))
        set_translated_text(self.copy_password_btn, "Copiar")

        stored_url = cred.get("url") or ""
        set_untranslated_text(self.detail_url, stored_url or "—")
        self.open_url_btn.setVisible(bool(stored_url))
        if cred.get("notes"):
            set_untranslated_text(self.detail_notes, cred["notes"])
        else:
            set_translated_text(self.detail_notes, "Sem anotações.")

        # Update buttons according to deleted state
        if cred.get("is_deleted"):
            self.edit_btn.hide()
            set_translated_text(self.delete_btn, "Excluir definitivamente")
            self.restore_btn.show()
        else:
            self.edit_btn.show()
            set_translated_text(self.delete_btn, "Excluir")
            self.restore_btn.hide()

        # Load history
        self.history_list.clear()
        hist = self.vault.db.get_password_history(cred_id)
        if hist:
            self.history_frame.show()
            for h in hist:
                import datetime
                dt = datetime.datetime.fromtimestamp(h["changed_at"]).strftime("%d/%m/%Y %H:%M")
                self.history_list.addItem(f"{dt} · senha anterior alterada")
        else:
            self.history_frame.hide()

    def _toggle_password_reveal(self):
        if self._pw_revealed:
            self._hide_password()
        else:
            self.detail_password.setText(self._raw_password)
            self.toggle_reveal_btn.setIcon(load_icon("reveal_off.svg"))
            self._pw_revealed = True
            self._reveal_timer.start()
            set_translated_text(self.toggle_reveal_btn, "Ocultar")

    def _hide_password(self):
        self._reveal_timer.stop()
        self.detail_password.setText("••••••••••••••••")
        self.toggle_reveal_btn.setIcon(load_icon("reveal_on.svg"))
        self._pw_revealed = False
        set_translated_text(self.toggle_reveal_btn, "Mostrar")

    def _copy_password(self):
        self.clipboard_auto_clear.copy_password(self._raw_password)

    def _copy_selected_password(self):
        if self.current_selected_id:
            self._copy_password()

    def _on_password_copied(self):
        seconds = self.settings_view.clipboard_timeout_seconds
        source = "Copiada" if seconds == 0 else f"Copiada ({seconds}s)"
        set_translated_text(self.copy_password_btn, source)

    def _on_clipboard_timer_finished(self):
        set_translated_text(self.copy_password_btn, "Copiar")

    def clear_sensitive_clipboard(self):
        self.clipboard_auto_clear.clear_if_unchanged()
        self.generator_view.clear_sensitive_data()
        self.cred_list.clear()
        self._raw_password = ""
        self.current_selected_id = None
        self._hide_password()
        if hasattr(self, "detail_password"):
            self.detail_password.clear()
            self.detail_username.clear()
            self.detail_url.clear()
            self.detail_notes.clear()
            self.history_list.clear()

    def _copy_username(self):
        if self.detail_username.text():
            QGuiApplication.clipboard().setText(self.detail_username.text())

    def _open_credential_url(self):
        if not self.current_selected_id or not self.vault.db:
            return
        credential = self.vault.db.get_credential(self.current_selected_id)
        url = credential.get("url", "") if credential else ""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            QMessageBox.warning(
                self, tr("Endereço inválido"),
                tr("Somente endereços HTTP ou HTTPS válidos podem ser abertos."),
            )
            return
        if not QDesktopServices.openUrl(QUrl(url)):
            QMessageBox.warning(
                self, tr("Não foi possível abrir"),
                tr("O sistema não conseguiu abrir este endereço."),
            )

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
                "Confirmar exclusão permanente",
                f"Excluir '{cred['title']}' permanentemente do cofre? Esta ação não pode ser desfeita.",
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
            answer = QMessageBox.question(
                self,
                "Mover para a lixeira",
                f"Mover '{cred['title']}' para a lixeira?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
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
            "Esvaziar lixeira",
            "Excluir permanentemente todos os itens? A remoção do cofre criptografado "
            "não garante a eliminação física de blocos antigos da memória flash.",
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
            set_translated_text(self.save_status_label, "● Alterações não salvas")
            self.save_status_label.setStyleSheet("color: #f59e0b; font-size: 12px; margin-right: 12px; font-weight: 600;")
        else:
            set_translated_text(self.save_status_label, "Alterações salvas")
            self.save_status_label.setStyleSheet("color: #34d399; font-size: 12px; margin-right: 12px;")

    def mark_saved(self):
        self._update_save_status()

    def _set_active_navigation(self, active_button: QPushButton) -> None:
        for button in (
            *self.nav_buttons,
        ):
            button.setStyleSheet(self._nav_button_style(button is active_button))

    def _set_list_toolbar_visible(self, visible: bool) -> None:
        for widget in (
            self.search_input,
            self.filter_combo,
            self.credentials_heading,
            self.save_status_label,
            self.save_btn,
            self.view_mode_btn,
        ):
            widget.setVisible(visible)

    def _show_current_list(self):
        if self.showing_deleted:
            self._show_trash_tab()
        else:
            self._show_credentials_tab()

    def _show_credentials_tab(self):
        self.showing_deleted = False
        self._set_active_navigation(self.nav_all_btn)
        set_translated_text(self.credentials_heading, "SENHAS SALVAS")
        self._set_list_toolbar_visible(True)
        self.add_btn.show()
        self.empty_trash_btn.hide()
        self.filter_combo.setCurrentIndex(0)
        self.filter_combo.show()
        self.main_stack.setCurrentWidget(self.credentials_page)
        self.refresh_list()

    def _show_trash_tab(self):
        self.showing_deleted = True
        self._set_active_navigation(self.nav_trash_btn)
        set_translated_text(self.credentials_heading, "LIXEIRA")
        self._set_list_toolbar_visible(True)
        self.add_btn.hide()
        self.empty_trash_btn.show()
        self.filter_combo.hide()
        self.main_stack.setCurrentWidget(self.credentials_page)
        self.refresh_list()

    def _show_settings_tab(self):
        self._set_active_navigation(self.nav_settings_btn)
        set_translated_text(self.credentials_heading, "CONFIGURAÇÕES")
        self._set_list_toolbar_visible(False)
        self.add_btn.hide()
        self.main_stack.setCurrentWidget(self.settings_view)

    def _show_generator(self):
        self._set_active_navigation(self.nav_generator_btn)
        set_translated_text(self.credentials_heading, "GERADOR DE SENHA")
        self._set_list_toolbar_visible(False)
        self.add_btn.hide()
        self.main_stack.setCurrentWidget(self.generator_view)

    def _show_usb(self):
        self._set_active_navigation(self.nav_usb_btn)
        set_translated_text(self.credentials_heading, "GERENCIAR COFRE USB")
        self._set_list_toolbar_visible(False)
        self.add_btn.hide()
        self.usb_view.refresh()
        self.main_stack.setCurrentWidget(self.usb_view)

    def _show_about(self):
        self._set_active_navigation(self.nav_about_btn)
        set_translated_text(self.credentials_heading, "SOBRE O CLAVIS")
        self._set_list_toolbar_visible(False)
        self.add_btn.hide()
        self.main_stack.setCurrentWidget(self.about_view)

    def _save_generated_password(self, password: str):
        title, accepted = QInputDialog.getText(self, "Salvar credencial", "Serviço:")
        if not accepted or not title.strip() or not self.vault.db:
            return
        username, accepted = QInputDialog.getText(self, "Salvar credencial", "Usuário (opcional):")
        if not accepted:
            return
        self.vault.db.add_credential(title, username, password)
        self.vault.has_unsaved_changes = True
        self._update_save_status()
        self.refresh_list()
        self._show_credentials_tab()

    def _export_vault(self):
        if not self.vault.path:
            return
        destination, _ = QFileDialog.getSaveFileName(
            self, "Exportar cópia KDBX", self.vault.path + ".backup",
            "Cofre KDBX (*.vault *.kdbx);;Todos os arquivos (*)",
        )
        if not destination:
            return
        if os.path.abspath(destination) == os.path.abspath(self.vault.path):
            QMessageBox.warning(self, "Exportação", "Escolha um destino diferente do cofre aberto.")
            return
        try:
            self.vault.save()
            with open(self.vault.path, "rb") as source_file:
                SafeVaultStorage.atomic_write_vault(
                    destination, source_file.read(), preserve_backup=True
                )
            QMessageBox.information(self, "Exportação concluída", "Cópia criptografada criada.")
        except Exception as error:
            QMessageBox.critical(self, "Falha na exportação", str(error))

    def _import_vault(self):
        source, _ = QFileDialog.getOpenFileName(
            self, "Importar de outro cofre KDBX", "",
            "Cofres KeePass (*.vault *.kdbx);;Todos os arquivos (*)",
        )
        if not source or os.path.abspath(source) == os.path.abspath(self.vault.path):
            return
        password, accepted = QInputDialog.getText(
            self, "Desbloquear cofre de origem", "Senha mestra:",
            QLineEdit.EchoMode.Password,
        )
        if not accepted or not self.vault.db:
            return
        source_vault = ClavisVault(source)
        try:
            source_vault.open_existing(password)
            imported_ids = []
            try:
                for deleted in (False, True):
                    for credential in source_vault.db.list_credentials(include_deleted=deleted):
                        new_id = self.vault.db.add_credential(
                            credential["title"], credential["username"],
                            credential["password"], credential["url"],
                            credential["notes"], is_deleted=deleted,
                        )
                        imported_ids.append(new_id)
                        history = source_vault.db.get_password_history(credential["id"])
                        if history:
                            self.vault.db.import_history(
                                new_id, [item["old_password"] for item in history]
                            )
            except Exception:
                for imported_id in imported_ids:
                    self.vault.db.permanently_delete_credential(imported_id)
                raise
            self.vault.has_unsaved_changes = True
            self._update_save_status()
            self.refresh_list()
            QMessageBox.information(self, "Importação concluída", "As credenciais foram adicionadas ao cofre aberto.")
        except Exception as error:
            QMessageBox.critical(self, "Falha na importação", str(error))
        finally:
            source_vault.lock()

    def _show_password_health(self):
        self._set_active_navigation(self.nav_health_btn)
        set_translated_text(self.credentials_heading, "SAÚDE DAS SENHAS")
        self._set_list_toolbar_visible(False)
        self.add_btn.hide()
        self.main_stack.setCurrentWidget(self.password_health_view)
        self._run_password_health_check()

    def _run_password_health_check(self):
        if not self.vault.db:
            return

        credentials = self.vault.db.list_credentials(include_deleted=False)
        findings = analyze_password_health(credentials)
        self.health_results.clear()
        self.health_total_value.setText(str(len(credentials)))

        if not credentials:
            self.health_weak_value.setText("0")
            self.health_reused_value.setText("0")
            set_translated_text(
                self.health_summary_label, "Não há credenciais ativas para analisar."
            )
            return
        weak = sum(any("Weak password" in issue for issue in f.issues) for f in findings)
        reused = sum("Reused password" in f.issues for f in findings)
        self.health_weak_value.setText(str(weak))
        self.health_reused_value.setText(str(reused))
        if not findings:
            set_translated_text(
                self.health_summary_label,
                "Nenhuma senha fraca ou reutilizada foi encontrada.",
            )
            return

        set_translated_text(
            self.health_summary_label,
            "{count} credencial(is) precisam de atenção. Selecione um item para abrir.",
            count=len(findings),
        )
        for finding in findings:
            item = QListWidgetItem(
                f"{finding.title}\n" + " · ".join(
                    tr({
                        "Weak password": "Senha fraca",
                        "Reused password": "Senha reutilizada",
                        "Could be stronger": "Pode ser mais forte",
                    }.get(issue, issue))
                    for issue in finding.issues
                )
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
