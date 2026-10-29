"""
Clavis Welcome and Vault Selection View (PySide6)
Allows the user to select a connected USB drive, create a new vault, or open an existing one.
"""

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QFrame
)

from ..usb import UsbManager
from .i18n import tr


class WelcomeView(QWidget):
    """Initial screen for selecting a USB drive and initiating vault open or creation."""

    vault_create_requested = Signal(str)  # target directory or vault path
    vault_open_requested = Signal(str)    # vault file path

    DARK_STYLE = """
        QFrame.card {
            background-color: #1a1c23;
            border: 1px solid #2a2d39;
            border-radius: 8px;
            padding: 24px;
        }
        QLabel.title {
            color: #f3f4f6;
            font-size: 24px;
            font-weight: 700;
        }
        QLabel.tagline {
            color: #9ca3af;
            font-size: 13px;
        }
        QComboBox {
            background-color: #121316;
            color: #e5e7eb;
            border: 1px solid #374151;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 13px;
        }
        QPushButton.primary {
            background-color: #4f46e5;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 10px 18px;
            font-weight: 600;
        }
        QPushButton.primary:hover {
            background-color: #4338ca;
        }
        QPushButton.secondary {
            background-color: #262933;
            color: #e5e7eb;
            border: 1px solid #374151;
            border-radius: 6px;
            padding: 10px 18px;
            font-weight: 500;
        }
        QPushButton.secondary:hover {
            background-color: #323644;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(self.DARK_STYLE)
        self._init_ui()
        self.refresh_drives()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)

        card = QFrame()
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card.setFixedWidth(520)

        logo_path = Path(__file__).resolve().parents[3] / "assets" / "ClavisLogoHQpng.png"
        logo_pixmap = QPixmap(str(logo_path))
        if logo_pixmap.isNull():
            raise RuntimeError(f"Unable to load Clavis logo: {logo_path}")

        title = QLabel()
        title.setPixmap(logo_pixmap.scaled(
            400,
            174,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tagline = QLabel("Seu cofre. Seu dispositivo. Seu controle.")
        tagline.setProperty("class", "tagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)


        card_layout.addWidget(title)
        card_layout.addWidget(tagline)

        desc = QLabel(
            "Clavis é um gerenciador local de senhas. Seu arquivo KDBX é criptografado "
            "e pode ser armazenado em uma unidade USB ou em outro local escolhido."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #9ca3af; font-size: 13px; line-height: 1.4;")
        card_layout.addWidget(desc)

        card_layout.addSpacing(8)

        # USB Drive Selector
        usb_label = QLabel("UNIDADE REMOVÍVEL / LOCAL DE ARMAZENAMENTO:")
        usb_label.setStyleSheet("color: #d1d5db; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
        card_layout.addWidget(usb_label)

        drive_row = QHBoxLayout()
        self.drive_combo = QComboBox()
        self.drive_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        refresh_btn = QPushButton("Atualizar")
        refresh_btn.setStyleSheet("background-color: #262933; color: #d1d5db; border: 1px solid #374151; padding: 8px 12px; border-radius: 6px;")
        refresh_btn.clicked.connect(self.refresh_drives)

        drive_row.addWidget(self.drive_combo, 1)
        drive_row.addWidget(refresh_btn)
        card_layout.addLayout(drive_row)

        # Action Buttons
        card_layout.addSpacing(12)
        btn_layout = QHBoxLayout()
        self.create_btn = QPushButton("Criar novo cofre")
        self.create_btn.setProperty("class", "primary")
        self.create_btn.clicked.connect(self._on_create)

        self.open_btn = QPushButton("Abrir cofre existente...")
        self.open_btn.setProperty("class", "secondary")
        self.open_btn.clicked.connect(self._on_open)

        btn_layout.addWidget(self.create_btn)
        btn_layout.addWidget(self.open_btn)
        card_layout.addLayout(btn_layout)

        # Transparency Notice
        notice = QLabel(
            "A unidade USB não protege contra malware ou keyloggers no computador. "
            "O cofre fica descriptografado em memória enquanto está desbloqueado."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet("color: #6b7280; font-size: 11px; margin-top: 12px;")
        card_layout.addWidget(notice)

        layout.addWidget(card)

    def refresh_drives(self):
        if not hasattr(self, "drive_combo"):
            return
        self.drive_combo.clear()
        drives = UsbManager.list_removable_drives()
        if drives:
            for d in drives:
                self.drive_combo.addItem(d.display_name, userData=d.mount_point)
        else:
            self.drive_combo.addItem(
                tr("Nenhuma unidade USB detectada (clique para procurar)"),
                userData=None,
            )

    def _on_create(self):
        mount = self.drive_combo.currentData()
        if not mount:
            # Allow user to pick directory manually
            directory = QFileDialog.getExistingDirectory(
                self, tr("Escolha a pasta do novo cofre")
            )
            if directory:
                mount = directory
            else:
                return

        default_path = os.path.join(mount, "clavis.vault")
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Criar cofre KDBX do Clavis"),
            default_path,
            "Clavis Vault (*.vault)"
        )
        if save_path:
            self.vault_create_requested.emit(save_path)

    def _on_open(self):
        vault_file, _ = QFileDialog.getOpenFileName(
            self,
            tr("Abrir cofre KDBX do Clavis"),
            "",
            "Clavis Vault (*.vault);;All Files (*)"
        )
        if vault_file:
            self.vault_open_requested.emit(vault_file)
