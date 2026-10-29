"""Compact utility pages that follow the Clavis dark visual system."""

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..password_generator import GeneratorOptions, PasswordGenerator
from .. import __version__
from ..usb import UsbManager
from ..vault import ClavisVault
from .clipboard import ClipboardAutoClear
from .i18n import apply_translations, set_translated_text


class PasswordGeneratorView(QWidget):
    save_requested = Signal(str)

    def __init__(self, clipboard: ClipboardAutoClear, parent=None):
        super().__init__(parent)
        self.clipboard = clipboard
        self.recent_passwords = []
        self._reveal_timer = QTimer(self)
        self._reveal_timer.setSingleShot(True)
        self._reveal_timer.setInterval(10_000)
        self._reveal_timer.timeout.connect(self._hide_after_timeout)
        self.setStyleSheet(_PAGE_STYLE)
        layout = QGridLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(14)
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 2)

        title = QLabel("Gerar senha")
        title.setObjectName("heading")
        layout.addWidget(title, 0, 0, 1, 2)
        intro = QLabel(
            "Crie senhas localmente com o módulo secrets. O histórico desta sessão é "
            "mantido apenas em memória e descartado ao bloquear o cofre."
        )
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        layout.addWidget(intro, 1, 0, 1, 2)

        options, option_layout = _section("OPÇÕES DE GERAÇÃO")
        length_row = QHBoxLayout()
        length_row.addWidget(QLabel("Comprimento"))
        self.length = QSpinBox()
        self.length.setRange(8, 128)
        self.length.setValue(20)
        length_row.addStretch()
        length_row.addWidget(self.length)
        option_layout.addLayout(length_row)
        self.lowercase = QCheckBox("Minúsculas")
        self.lowercase.setChecked(True)
        self.uppercase = QCheckBox("Maiúsculas")
        self.uppercase.setChecked(True)
        self.digits = QCheckBox("Números")
        self.digits.setChecked(True)
        self.symbols = QCheckBox("Símbolos")
        self.symbols.setChecked(True)
        self.exclude_ambiguous = QCheckBox("Excluir caracteres ambíguos")
        self.exclude_ambiguous.setChecked(True)
        for checkbox in (self.lowercase, self.uppercase, self.digits, self.symbols, self.exclude_ambiguous):
            option_layout.addWidget(checkbox)
        layout.addWidget(options, 2, 0)

        result, result_layout = _section("SENHA GERADA")
        self.output = QLineEdit()
        self.output.setReadOnly(True)
        self.output.setEchoMode(QLineEdit.EchoMode.Password)
        self.output.setPlaceholderText("Clique em gerar para criar uma senha")
        result_layout.addWidget(self.output)
        self.result_label = QLabel("O resultado fica visível apenas nesta sessão.")
        self.result_label.setObjectName("muted")
        result_layout.addWidget(self.result_label)
        buttons = QHBoxLayout()
        self.generate_button = QPushButton("Gerar senha")
        self.generate_button.clicked.connect(self.generate)
        self.reveal_button = QPushButton("Mostrar")
        self.reveal_button.setCheckable(True)
        self.reveal_button.toggled.connect(self._toggle_reveal)
        self.copy_button = QPushButton("Copiar")
        self.copy_button.clicked.connect(self._copy)
        self.save_button = QPushButton("Salvar como credencial")
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(self.generate_button)
        buttons.addWidget(self.reveal_button)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.save_button)
        result_layout.addLayout(buttons)
        layout.addWidget(result, 2, 1)

        self.history_label = QLabel("Histórico recente: nenhum")
        self.history_label.setObjectName("muted")
        self.history_label.setWordWrap(True)
        layout.addWidget(self.history_label, 3, 1)
        layout.setRowStretch(4, 1)
        apply_translations(self)

    def generate(self):
        options = GeneratorOptions(
            length=self.length.value(),
            use_lowercase=self.lowercase.isChecked(),
            use_uppercase=self.uppercase.isChecked(),
            use_digits=self.digits.isChecked(),
            use_symbols=self.symbols.isChecked(),
            exclude_ambiguous=self.exclude_ambiguous.isChecked(),
        )
        try:
            password = PasswordGenerator.generate(options)
        except ValueError as error:
            set_translated_text(self.result_label, str(error))
            return
        self.output.setText(password)
        self.recent_passwords.insert(0, password)
        del self.recent_passwords[5:]
        set_translated_text(
            self.history_label,
            "Histórico recente desta sessão: {count} senha(s).",
            count=len(self.recent_passwords),
        )

    def _toggle_reveal(self, revealed: bool):
        self.output.setEchoMode(
            QLineEdit.EchoMode.Normal if revealed else QLineEdit.EchoMode.Password
        )
        set_translated_text(
            self.reveal_button, "Ocultar" if revealed else "Mostrar"
        )
        if revealed:
            self._reveal_timer.start()
        else:
            self._reveal_timer.stop()

    def _hide_after_timeout(self):
        self.reveal_button.setChecked(False)

    def _copy(self):
        self.clipboard.copy_password(self.output.text())

    def _save(self):
        if self.output.text():
            self.save_requested.emit(self.output.text())

    def clear_sensitive_data(self):
        self._reveal_timer.stop()
        self.reveal_button.setChecked(False)
        self.output.clear()
        self.recent_passwords.clear()
        set_translated_text(self.history_label, "Histórico recente: nenhum")


class VaultManagementView(QWidget):
    import_requested = Signal()
    export_requested = Signal()

    def __init__(self, vault: ClavisVault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.setStyleSheet(_PAGE_STYLE)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(14)
        title = QLabel("Cofre USB")
        title.setObjectName("heading")
        self.layout.addWidget(title)
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        self.summary.setWordWrap(True)
        self.layout.addWidget(self.summary)
        actions, action_layout = _section("BACKUP E TRANSFERÊNCIA")
        note = QLabel(
            "Exportar cria uma cópia criptografada KDBX. Importar mescla as credenciais "
            "de outro cofre KDBX aberto pelo usuário; o arquivo atual não é substituído."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        action_layout.addWidget(note)
        buttons = QHBoxLayout()
        export_button = QPushButton("Exportar cópia criptografada")
        export_button.clicked.connect(self.export_requested.emit)
        import_button = QPushButton("Importar de outro cofre")
        import_button.clicked.connect(self.import_requested.emit)
        buttons.addWidget(export_button)
        buttons.addWidget(import_button)
        action_layout.addLayout(buttons)
        self.layout.addWidget(actions)
        self.layout.addStretch()
        self.refresh()

    def refresh(self):
        path = self.vault.path
        try:
            stat = os.stat(path)
            modified = datetime.fromtimestamp(stat.st_mtime).astimezone().strftime("%d/%m/%Y %H:%M")
            metadata = self.vault.db.metadata if self.vault.db else {}
            absolute_path = os.path.normcase(os.path.abspath(path))
            device = next(
                (
                    candidate for candidate in UsbManager.list_removable_drives()
                    if absolute_path.startswith(
                        os.path.normcase(os.path.abspath(candidate.mount_point)).rstrip("\\/")
                        + os.sep
                    )
                ),
                None,
            )
            device_info = (
                f"{device.display_name} · {device.filesystem} · "
                f"{device.free_bytes:,} bytes livres"
                if device else "Não identificada como unidade removível"
            )
            set_translated_text(
                self.summary,
                "Arquivo: {path}\nTamanho: {size:,} bytes\n"
                "Última modificação: {modified}\n"
                "Dispositivo: {device}\n"
                "Formato: KDBX {version} · Cifra: {encryption}",
                path=path,
                size=stat.st_size,
                modified=modified,
                device=device_info,
                version=metadata.get("version", "desconhecido"),
                encryption=metadata.get("encryption") or "desconhecida",
            )
        except OSError as error:
            set_translated_text(
                self.summary,
                "Não foi possível consultar o arquivo do cofre: {error}",
                error=error,
            )


class AboutView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_PAGE_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        title = QLabel("Sobre o Clavis")
        title.setObjectName("heading")
        brand_row = QHBoxLayout()
        logo_path = Path(__file__).resolve().parents[3] / "assets" / "favicon.png"
        pixmap = QPixmap(str(logo_path))
        logo = QLabel()
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(
                40, 40,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        brand_row.addWidget(logo)
        brand_row.addWidget(title)
        brand_row.addStretch()
        layout.addLayout(brand_row)
        info, info_layout = _section("CLAVIS · GERENCIADOR LOCAL DE SENHAS")
        description = QLabel(
            "Aplicativo local para administrar credenciais em cofres KeePass KDBX. "
            "O aplicativo não envia dados para serviços remotos."
        )
        description.setObjectName("muted")
        description.setWordWrap(True)
        info_layout.addWidget(description)
        tech = QLabel("Tecnologias: Python · PySide6 · PyKeePass · formato KDBX")
        tech.setObjectName("muted")
        info_layout.addWidget(tech)
        version = QLabel(f"Versão {__version__}")
        version.setObjectName("muted")
        info_layout.addWidget(version)
        shortcuts = QLabel(
            "Atalhos\nCtrl+N  Nova credencial\nCtrl+F  Buscar\nCtrl+L  Bloquear cofre\n"
            "Ctrl+E  Instruções de ejeção segura\nAlt+C  Copiar senha selecionada"
        )
        shortcuts.setObjectName("muted")
        info_layout.addWidget(shortcuts)
        safety = QLabel(
            "Python não garante apagamento seguro da memória; swap, dumps e um dispositivo "
            "comprometido podem expor dados enquanto o cofre está desbloqueado."
        )
        safety.setObjectName("muted")
        safety.setWordWrap(True)
        info_layout.addWidget(safety)
        layout.addWidget(info)
        layout.addStretch()
        apply_translations(self)


def _section(title: str):
    frame = QFrame()
    frame.setObjectName("section")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 14)
    layout.setSpacing(10)
    heading = QLabel(title)
    heading.setObjectName("sectionTitle")
    layout.addWidget(heading)
    return frame, layout


_PAGE_STYLE = """
    QWidget { background: #08090a; color: #e8eaed; }
    QFrame#section { background: #0e1113; border: 1px solid #252a2d; border-radius: 8px; }
    QLabel#heading { color: #f3f4f6; font-size: 22px; font-weight: 700; }
    QLabel#sectionTitle { color: #9da5aa; font-size: 11px; font-weight: 700; }
    QLabel#muted { color: #9da5aa; font-size: 12px; }
    QLineEdit, QSpinBox { background: #08090a; border: 1px solid #30373b; border-radius: 5px; padding: 8px; color: #e8eaed; }
    QCheckBox { color: #d3d8db; spacing: 8px; }
    QPushButton { background: #284cff; border: 0; border-radius: 5px; color: white; padding: 8px 14px; font-weight: 600; }
    QPushButton:hover { background: #3d5dff; }
"""
