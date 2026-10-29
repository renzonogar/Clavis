"""Portuguese settings and security information for the unlocked vault."""

import os
from datetime import datetime

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..vault import ClavisVault
from .i18n import (
    current_language,
    set_language,
    apply_translations,
    set_translated_text,
    tr,
)
from .ui_scale import MAX_UI_SCALE, MIN_UI_SCALE, UI_SCALE_STEP, recommended_ui_scale


class SettingsView(QWidget):
    timeout_changed = Signal(int)
    clipboard_timeout_changed = Signal(int)
    font_size_changed = Signal(int)
    language_changed = Signal(str)
    master_password_change_requested = Signal(str)

    def __init__(self, vault: ClavisVault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.settings = QSettings("Clavis", "Clavis")
        self._init_ui()

    @property
    def timeout_seconds(self) -> int:
        return int(self.settings.value("security/auto_lock_seconds", 300))

    @property
    def clipboard_timeout_seconds(self) -> int:
        return int(self.settings.value("security/clipboard_seconds", 30))

    @property
    def font_size(self) -> int:
        return int(self.settings.value("ui/font_size", 10))

    @property
    def ui_scale(self) -> str:
        return str(self.settings.value("ui/scale_percent", "recommended"))

    @property
    def backup_enabled(self) -> bool:
        return self.settings.value("storage/create_backup", True, type=bool)

    def _init_ui(self):
        self.setStyleSheet("""
            QWidget { background: #08090a; color: #e8eaed; }
            QFrame#section { background: #0e1113; border: 1px solid #252a2d; border-radius: 8px; }
            QLabel#heading { color: #f3f4f6; font-size: 22px; font-weight: 700; }
            QLabel#sectionTitle { color: #9da5aa; font-size: 11px; font-weight: 700; }
            QLabel#muted { color: #9da5aa; font-size: 12px; }
            QComboBox, QLineEdit { background: #08090a; border: 1px solid #30373b; border-radius: 5px; padding: 8px; color: #e8eaed; }
            QPushButton { background: #284cff; border: 0; border-radius: 5px; color: white; padding: 8px 14px; font-weight: 600; }
            QPushButton:hover { background: #3d5dff; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QGridLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(14)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        heading = QLabel("Configurações")
        heading.setObjectName("heading")
        layout.addWidget(heading, 0, 0, 1, 2)

        language_box, language_layout = self._section("IDIOMA DA INTERFACE")
        language_row = QHBoxLayout()
        language_row.addWidget(QLabel("Idioma"))
        language_row.addStretch()
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Português (Brasil)", "pt_BR")
        self._select_data(self.language_combo, current_language())
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        language_row.addWidget(self.language_combo)
        language_layout.addLayout(language_row)
        layout.addWidget(language_box, 1, 0)

        security, security_layout = self._section("SESSÃO E PRIVACIDADE")
        auto_row = QHBoxLayout()
        auto_row.addWidget(QLabel("Bloquear após inatividade"))
        auto_row.addStretch()
        self.timeout_combo = QComboBox()
        for label, seconds in (
            ("1 minuto", 60), ("5 minutos", 300), ("15 minutos", 900),
            ("30 minutos", 1800), ("Nunca (menos seguro)", 0),
        ):
            self.timeout_combo.addItem(label, seconds)
        self._select_data(self.timeout_combo, self.timeout_seconds)
        self.timeout_combo.currentIndexChanged.connect(self._on_timeout_changed)
        auto_row.addWidget(self.timeout_combo)
        security_layout.addLayout(auto_row)

        clipboard_row = QHBoxLayout()
        clipboard_row.addWidget(QLabel("Limpar senha copiada após"))
        clipboard_row.addStretch()
        self.clipboard_combo = QComboBox()
        for label, seconds in (
            ("15 segundos", 15), ("30 segundos", 30), ("1 minuto", 60),
            ("2 minutos", 120), ("Não limpar automaticamente", 0),
        ):
            self.clipboard_combo.addItem(label, seconds)
        self._select_data(self.clipboard_combo, self.clipboard_timeout_seconds)
        self.clipboard_combo.currentIndexChanged.connect(self._on_clipboard_timeout_changed)
        clipboard_row.addWidget(self.clipboard_combo)
        security_layout.addLayout(clipboard_row)
        note = QLabel(
            "A senha só é removida se a área de transferência ainda contiver o valor copiado pelo Clavis."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        security_layout.addWidget(note)
        layout.addWidget(security, 2, 0)

        preferences, preferences_layout = self._section("INTERFACE E BACKUP")
        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Escala da interface"))
        scale_row.addStretch()
        self.scale_combo = QComboBox()
        self.scale_combo.addItem("Recomendado", "recommended")
        for percent in range(
            MIN_UI_SCALE, MAX_UI_SCALE + 1, UI_SCALE_STEP
        ):
            self.scale_combo.addItem(f"{percent}%", str(percent))
        self._select_data(self.scale_combo, self.ui_scale)
        self.scale_combo.currentIndexChanged.connect(self._on_scale_changed)
        scale_row.addWidget(self.scale_combo)
        preferences_layout.addLayout(scale_row)
        self.scale_recommendation_label = QLabel()
        self.scale_recommendation_label.setObjectName("muted")
        self.scale_recommendation_label.setWordWrap(True)
        preferences_layout.addWidget(self.scale_recommendation_label)
        self._update_scale_recommendation()

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Tamanho da fonte"))
        font_row.addStretch()
        self.font_combo = QComboBox()
        for size in (9, 10, 11, 12, 13, 14):
            self.font_combo.addItem(f"{size} pt", size)
        self._select_data(self.font_combo, self.font_size)
        self.font_combo.currentIndexChanged.connect(self._on_font_size_changed)
        font_row.addWidget(self.font_combo)
        preferences_layout.addLayout(font_row)
        self.backup_checkbox = QCheckBox("Preservar arquivo .bak antes de substituir o cofre")
        self.backup_checkbox.setChecked(self.backup_enabled)
        self.backup_checkbox.toggled.connect(
            lambda checked: self.settings.setValue("storage/create_backup", checked)
        )
        preferences_layout.addWidget(self.backup_checkbox)
        layout.addWidget(preferences, 3, 0)

        password_box, password_layout = self._section("SENHA MESTRA")
        password_note = QLabel(
            "A alteração regrava o arquivo KDBX com a nova senha mestra. Use uma senha longa e exclusiva."
        )
        password_note.setObjectName("muted")
        password_note.setWordWrap(True)
        password_layout.addWidget(password_note)
        self.new_pw_input = QLineEdit()
        self.new_pw_input.setPlaceholderText("Nova senha mestra (mínimo 12 caracteres)")
        self.new_pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_pw_input = QLineEdit()
        self.confirm_pw_input.setPlaceholderText("Confirme a nova senha mestra")
        self.confirm_pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(self.new_pw_input)
        password_layout.addWidget(self.confirm_pw_input)
        change_button = QPushButton("Alterar senha mestra")
        change_button.clicked.connect(self._on_change_password)
        password_layout.addWidget(change_button, 0)
        layout.addWidget(password_box, 4, 0)

        info_box, info_layout = self._section("ARQUIVO DO COFRE")
        metadata = self.vault.db.metadata if self.vault.db else {}
        stat = os.stat(self.vault.path) if self.vault.path and os.path.exists(self.vault.path) else None
        modified = datetime.fromtimestamp(stat.st_mtime).astimezone().strftime("%d/%m/%Y %H:%M") if stat else "indisponível"
        rows = (
            ("Caminho", self.vault.path or "indisponível"),
            ("Tamanho", f"{stat.st_size:,} bytes" if stat else "indisponível"),
            ("Modificado", modified),
            ("Formato", f"KDBX {metadata.get('version', 'desconhecido')}"),
            ("Cifra identificada", str(metadata.get("encryption") or "desconhecida")),
            ("Derivação de chave", str(metadata.get("kdf") or "desconhecida")),
        )
        for label, value in rows:
            row = QHBoxLayout()
            name = QLabel(label)
            name.setObjectName("muted")
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            row.addWidget(name, 0)
            row.addWidget(value_label, 1)
            info_layout.addLayout(row)
        layout.addWidget(info_box, 1, 1)

        limits_box, limits_layout = self._section("LIMITAÇÕES DE SEGURANÇA")
        limits = QLabel(
            "O cofre é mantido em memória enquanto está desbloqueado. Python não garante "
            "apagamento seguro da memória; o sistema operacional pode usar paginação/swap "
            "ou gerar dumps. Malware, keyloggers e captura de tela no dispositivo desbloqueado "
            "podem expor dados. Mantenha backups criptografados e proteja a unidade física."
        )
        limits.setObjectName("muted")
        limits.setWordWrap(True)
        limits_layout.addWidget(limits)
        layout.addWidget(limits_box, 2, 1)
        layout.setRowStretch(5, 1)

        scroll.setWidget(container)
        root.addWidget(scroll)
        apply_translations(self)

    def _section(self, title: str):
        frame = QFrame()
        frame.setObjectName("section")
        section_layout = QVBoxLayout(frame)
        section_layout.setContentsMargins(14, 12, 14, 14)
        section_layout.setSpacing(10)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        section_layout.addWidget(label)
        return frame, section_layout

    @staticmethod
    def _select_data(combo: QComboBox, value: object):
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    def _on_timeout_changed(self, index: int):
        seconds = int(self.timeout_combo.itemData(index))
        self.settings.setValue("security/auto_lock_seconds", seconds)
        self.timeout_changed.emit(seconds)

    def _on_clipboard_timeout_changed(self, index: int):
        seconds = int(self.clipboard_combo.itemData(index))
        self.settings.setValue("security/clipboard_seconds", seconds)
        self.clipboard_timeout_changed.emit(seconds)

    def _on_font_size_changed(self, index: int):
        size = int(self.font_combo.itemData(index))
        self.settings.setValue("ui/font_size", size)
        self.font_size_changed.emit(size)

    def _on_scale_changed(self, index: int):
        scale = str(self.scale_combo.itemData(index))
        self.settings.setValue("ui/scale_percent", scale)
        QMessageBox.information(
            self,
            tr("Escala da interface"),
            tr("Reinicie o Clavis para aplicar a nova escala da interface."),
        )

    def _update_scale_recommendation(self):
        set_translated_text(
            self.scale_recommendation_label,
            "Recomendado para esta tela: {scale}%. Reinicie o Clavis para aplicar alterações.",
            scale=recommended_ui_scale(),
        )

    def _on_language_changed(self, index: int):
        language = str(self.language_combo.itemData(index))
        set_language(language)
        self.settings.setValue("interface/language", language)
        self.language_changed.emit(language)

    def _on_change_password(self):
        password = self.new_pw_input.text()
        if len(password) < 12:
            QMessageBox.warning(
                self, tr("Senha inválida"), tr("Use pelo menos 12 caracteres.")
            )
            return
        if password != self.confirm_pw_input.text():
            QMessageBox.warning(
                self, tr("Confirmação"),
                tr("As senhas informadas não coincidem."),
            )
            return
        self.master_password_change_requested.emit(password)
        self.new_pw_input.clear()
        self.confirm_pw_input.clear()
