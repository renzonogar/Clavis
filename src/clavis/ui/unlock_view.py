"""
Clavis Unlock and Master Password View (PySide6)
Presents master password input for both opening existing vaults and creating new vaults.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame
)
from .i18n import set_translated_text, set_untranslated_text, tr


class UnlockView(QWidget):
    """Handles master password entry for vault unlocking or initial creation."""

    unlock_submitted = Signal(str)           # master_password
    create_submitted = Signal(str, str)      # master_password, confirm_password
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_creation_mode = False
        self.target_vault_path = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)

        card = QFrame()
        card.setFixedWidth(520)
        card.setStyleSheet("""
            QFrame {
                background-color: #1a1c23;
                border: 1px solid #2a2d39;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                color: #e5e7eb;
            }
            QLineEdit {
                background-color: #121316;
                color: #f3f4f6;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #6366f1;
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
                color: #9ca3af;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px 14px;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(14)

        self.title_label = QLabel("Desbloquear cofre Clavis")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #f9fafb;"
        )
        card_layout.addWidget(self.title_label)

        self.path_label = QLabel("")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        card_layout.addWidget(self.path_label)

        # Master Password Input
        self.pw_label = QLabel("Senha mestra:")
        card_layout.addWidget(self.pw_label)

        pw_row = QHBoxLayout()
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.returnPressed.connect(self._on_submit)

        self.toggle_pw_btn = QPushButton("Mostrar")
        self.toggle_pw_btn.setFixedWidth(60)
        self.toggle_pw_btn.setStyleSheet("background-color: #262933; color: #9ca3af; border: 1px solid #374151; border-radius: 6px; padding: 8px;")
        self.toggle_pw_btn.clicked.connect(self._toggle_show_pw)

        pw_row.addWidget(self.pw_input, 1)
        pw_row.addWidget(self.toggle_pw_btn)
        card_layout.addLayout(pw_row)

        # Confirmation input (shown in creation mode)
        self.confirm_label = QLabel("Confirme a senha mestra:")
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.returnPressed.connect(self._on_submit)
        card_layout.addWidget(self.confirm_label)
        card_layout.addWidget(self.confirm_input)

        # Guidance text
        self.guidance_label = QLabel(
            "Não há senha de recuperação. Se perder a senha mestra, não será possível "
            "desbloquear o cofre."
        )
        self.guidance_label.setWordWrap(True)
        self.guidance_label.setStyleSheet("color: #ef4444; font-size: 11px; margin-top: 4px;")
        card_layout.addWidget(self.guidance_label)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #f87171; font-size: 12px; font-weight: 500;")
        self.error_label.hide()
        card_layout.addWidget(self.error_label)

        # Buttons
        btn_row = QHBoxLayout()
        self.back_btn = QPushButton("Voltar")
        self.back_btn.setProperty("class", "secondary")
        self.back_btn.clicked.connect(self.back_requested.emit)

        self.action_btn = QPushButton("Desbloquear cofre")
        self.action_btn.setProperty("class", "primary")
        self.action_btn.clicked.connect(self._on_submit)

        btn_row.addWidget(self.back_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.action_btn)
        card_layout.addLayout(btn_row)

        layout.addWidget(card)

    def set_mode(self, is_creation: bool, vault_path: str):
        self.is_creation_mode = is_creation
        self.target_vault_path = vault_path
        self.pw_input.clear()
        self.confirm_input.clear()
        self.error_label.hide()
        set_untranslated_text(self.path_label, vault_path)

        if is_creation:
            set_translated_text(self.title_label, "Definir senha mestra do cofre")
            self.confirm_label.show()
            self.confirm_input.show()
            set_translated_text(self.action_btn, "Criar cofre KDBX")
            set_translated_text(
                self.guidance_label,
                "Escolha uma senha longa e exclusiva (12 caracteres ou mais). Não há "
                "recuperação caso seja esquecida."
            )
        else:
            set_translated_text(self.title_label, "Desbloquear cofre Clavis")
            self.confirm_label.hide()
            self.confirm_input.hide()
            set_translated_text(self.action_btn, "Desbloquear cofre")
            set_translated_text(
                self.guidance_label,
                "Os dados são carregados em memória enquanto o cofre está aberto. "
                "Python e o sistema operacional não garantem que páginas de memória "
                "ou dumps não sejam gravados em disco."
            )

    def show_error(self, message: str):
        set_untranslated_text(self.error_label, tr(message))
        self.error_label.show()

    def _toggle_show_pw(self):
        if self.pw_input.echoMode() == QLineEdit.EchoMode.Password:
            self.pw_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.confirm_input.setEchoMode(QLineEdit.EchoMode.Normal)
            set_translated_text(self.toggle_pw_btn, "Ocultar")
        else:
            self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
            set_translated_text(self.toggle_pw_btn, "Mostrar")

    def _on_submit(self):
        pw = self.pw_input.text()
        if not pw:
            self.show_error("A senha mestra não pode ficar vazia.")
            return

        if self.is_creation_mode:
            confirm = self.confirm_input.text()
            if pw != confirm:
                self.show_error("As senhas não coincidem. Verifique a confirmação.")
                return
            if len(pw) < 8:
                self.show_error("Use uma senha mestra com pelo menos 12 caracteres.")
                return
            self.create_submitted.emit(pw, confirm)
        else:
            self.unlock_submitted.emit(pw)
