"""
Clavis Add/Edit Credential Dialog (PySide6)
Form for credential creation and modification, with integrated cryptographically
secure password generator and real-time strength estimation.
"""

from typing import Optional, Dict, Any

from PySide6.QtCore import QEasingCurve, Qt, QParallelAnimationGroup, QPropertyAnimation, QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QCheckBox, QSlider, QFrame, QMessageBox,
    QScrollArea, QWidget, QGraphicsOpacityEffect
)

from clavis.ui.icons import load_icon

from ..password_generator import PasswordGenerator, GeneratorOptions
from .clipboard import ClipboardAutoClear


class CredentialDialog(QDialog):
    """Dialog for creating or updating a credential entry."""

    def __init__(
        self,
        parent=None,
        existing_credential: Optional[Dict[str, Any]] = None,
        clipboard_auto_clear: Optional[ClipboardAutoClear] = None,
    ):
        super().__init__(parent)
        self.existing_credential = existing_credential
        self.clipboard_auto_clear = clipboard_auto_clear or ClipboardAutoClear(self)
        is_editing = existing_credential is not None
        self.setWindowTitle("Edit Credential" if is_editing else "New Credential")
        self._animation_group: Optional[QParallelAnimationGroup] = None
        if is_editing:
            self.setModal(True)
            self.setWindowFlags(
                Qt.WindowType.Dialog
                | Qt.WindowType.CustomizeWindowHint
                | Qt.WindowType.FramelessWindowHint
            )
            self._opacity_effect = QGraphicsOpacityEffect(self)
            self._opacity_effect.setOpacity(1.0)
            self.setGraphicsEffect(self._opacity_effect)

        self.setMinimumWidth(500)
        self._init_ui()
        self._fit_available_screen()
        self.clipboard_auto_clear.copied.connect(self._on_password_copied)
        self.clipboard_auto_clear.timer_finished.connect(self._on_clipboard_timer_finished)

        if existing_credential:
            self._populate_fields(existing_credential)

    def showEvent(self, event):
        super().showEvent(event)
        if self.existing_credential is None:
            return

        final_geometry = self.geometry()
        parent = self.parentWidget()
        if parent is not None:
            center = parent.mapToGlobal(parent.rect().center())
        else:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                return
            center = screen.availableGeometry().center()
        final_geometry.moveCenter(center)

        initial_geometry = QRect(final_geometry)
        initial_geometry.adjust(10, 5, -10, -5)
        self.setGeometry(initial_geometry)
        self._opacity_effect.setOpacity(0.0)

        zoom = QPropertyAnimation(self, b"geometry", self)
        zoom.setDuration(180)
        zoom.setStartValue(initial_geometry)
        zoom.setEndValue(final_geometry)
        zoom.setEasingCurve(QEasingCurve.Type.OutCubic)

        fade = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        fade.setDuration(180)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._animation_group = QParallelAnimationGroup(self)
        self._animation_group.addAnimation(zoom)
        self._animation_group.addAnimation(fade)
        self._animation_group.start()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        self.setStyleSheet("""
            QDialog {
                background-color: #1a1c23;
                color: #e5e7eb;
                border: 2px solid #4a4a4a;
                border-radius: 12px;
            }
            QLabel {
                color: #d1d5db;
                font-size: 12px;
                font-weight: 500;
            }
            QLineEdit, QTextEdit {
                background-color: #121316;
                color: #f3f4f6;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border-color: #6366f1;
            }
            QCheckBox {
                color: #9ca3af;
                font-size: 12px;
            }
            QPushButton.primary {
                background-color: #4f46e5;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton.primary:hover {
                background-color: #4338ca;
            }
            QPushButton.secondary {
                background-color: #262933;
                color: #d1d5db;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 8px 14px;
            }
        """)

        form = QWidget()
        form.setObjectName("credentialForm")
        form.setStyleSheet("background-color: #1a1c23;")
        form.setAutoFillBackground(True)
        form_layout = QVBoxLayout(form)
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(4, 4, 4, 4)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet(
            "QScrollArea { background-color: #1a1c23; border: none; }"
        )
        scroll_area.viewport().setStyleSheet("background-color: #1a1c23;")
        scroll_area.setWidget(form)
        layout.addWidget(scroll_area, 1)

        # Title
        form_layout.addWidget(QLabel("Title / Service Name *"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("e.g. GitHub, ProtonMail, Bank")
        form_layout.addWidget(self.title_input)

        # Username
        form_layout.addWidget(QLabel("Username / Email *"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("e.g. user@example.com")
        form_layout.addWidget(self.username_input)

        # Password Row
        form_layout.addWidget(QLabel("Password *"))
        pw_row = QHBoxLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.textChanged.connect(self._on_password_changed)

        self.toggle_pw_btn = QPushButton("")
        self.toggle_pw_btn.setFixedWidth(55)
        self.toggle_pw_btn.setProperty("class", "secondary")
        self.toggle_pw_btn.clicked.connect(self._toggle_pw_visibility)
        self.toggle_pw_btn.setIcon(load_icon("reveal_on.svg"))

        self.copy_pw_btn = QPushButton("")
        self.copy_pw_btn.setFixedWidth(55)
        self.copy_pw_btn.setProperty("class", "secondary")
        self.copy_pw_btn.clicked.connect(self._copy_password)
        self.copy_pw_btn.setIcon(load_icon("copy.svg"))

        pw_row.addWidget(self.password_input, 1)
        pw_row.addWidget(self.toggle_pw_btn)
        pw_row.addWidget(self.copy_pw_btn)
        form_layout.addLayout(pw_row)

        # Strength Bar & Feedback
        self.strength_label = QLabel("Strength: Empty")
        self.strength_label.setStyleSheet("color: #9ca3af; font-size: 11px;")
        form_layout.addWidget(self.strength_label)

        # Generator Accordion / Frame
        gen_box = QFrame()
        gen_box.setStyleSheet("background-color: #121316; border: 1px solid #2a2d39; border-radius: 6px; padding: 12px;")
        gen_layout = QVBoxLayout(gen_box)
        gen_layout.setSpacing(8)

        gen_title_row = QHBoxLayout()
        gen_title_label = QLabel("Password Generator (CSPRNG)")
        gen_title_label.setStyleSheet("font-weight: 600; color: #a5b4fc;")
        self.gen_btn = QPushButton("Generate New")
        self.gen_btn.setProperty("class", "secondary")
        self.gen_btn.clicked.connect(self._generate_password)

        gen_title_row.addWidget(gen_title_label)
        gen_title_row.addStretch()
        gen_title_row.addWidget(self.gen_btn)
        gen_layout.addLayout(gen_title_row)

        # Length slider
        len_row = QHBoxLayout()
        self.len_label = QLabel("Length: 20")
        self.len_slider = QSlider(Qt.Orientation.Horizontal)
        self.len_slider.setRange(8, 64)
        self.len_slider.setValue(20)
        self.len_slider.valueChanged.connect(lambda v: self.len_label.setText(f"Length: {v}"))
        len_row.addWidget(self.len_label)
        len_row.addWidget(self.len_slider, 1)
        gen_layout.addLayout(len_row)

        # Checkboxes
        opts_row = QHBoxLayout()
        self.chk_upper = QCheckBox("A-Z")
        self.chk_upper.setChecked(True)
        self.chk_lower = QCheckBox("a-z")
        self.chk_lower.setChecked(True)
        self.chk_digits = QCheckBox("0-9")
        self.chk_digits.setChecked(True)
        self.chk_symbols = QCheckBox("!@#$")
        self.chk_symbols.setChecked(True)
        self.chk_ambiguous = QCheckBox("No Ambiguous")
        self.chk_ambiguous.setChecked(True)

        opts_row.addWidget(self.chk_upper)
        opts_row.addWidget(self.chk_lower)
        opts_row.addWidget(self.chk_digits)
        opts_row.addWidget(self.chk_symbols)
        opts_row.addWidget(self.chk_ambiguous)
        gen_layout.addLayout(opts_row)

        form_layout.addWidget(gen_box)

        # URL
        form_layout.addWidget(QLabel("Website URL (Optional)"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://...")
        form_layout.addWidget(self.url_input)

        # Notes
        form_layout.addWidget(QLabel("Notes (Optional)"))
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        self.notes_input.setPlaceholderText("Recovery codes, security questions, notes...")
        form_layout.addWidget(self.notes_input)

        # Buttons
        btn_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setProperty("class", "secondary")
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Save Credential")
        self.save_btn.setProperty("class", "primary")
        self.save_btn.clicked.connect(self._on_save)

        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

    def _fit_available_screen(self):
        screen = self.parentWidget().screen() if self.parentWidget() else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        max_width = max(self.minimumWidth(), available.width() - 48)
        max_height = max(320, available.height() - 48)
        self.resize(
            min(max(self.sizeHint().width(), self.minimumWidth()), max_width),
            min(self.sizeHint().height(), max_height),
        )

    def _populate_fields(self, cred: Dict[str, Any]):
        self.title_input.setText(cred.get("title", ""))
        self.username_input.setText(cred.get("username", ""))
        self.password_input.setText(cred.get("password", ""))
        self.url_input.setText(cred.get("url", ""))
        self.notes_input.setPlainText(cred.get("notes", ""))
        self._on_password_changed(cred.get("password", ""))

    def _toggle_pw_visibility(self):
        if self.password_input.echoMode() == QLineEdit.EchoMode.Password:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_pw_btn.setIcon(load_icon("reveal_off.svg"))
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_pw_btn.setIcon(load_icon("reveal_on.svg"))

    def _copy_password(self):
        self.clipboard_auto_clear.copy_password(self.password_input.text())

    def _on_password_copied(self):
        self.copy_pw_btn.setText("Copied (30s)")

    def _on_clipboard_timer_finished(self):
        self.copy_pw_btn.setText("Copy")

    def _on_password_changed(self, text: str):
        analysis = PasswordGenerator.estimate_strength(text)
        colors = {
            "Empty": "#9ca3af",
            "Very Weak": "#ef4444",
            "Weak": "#f97316",
            "Fair": "#eab308",
            "Strong": "#10b981",
            "Very Strong": "#06b6d4"
        }
        color = colors.get(analysis["label"], "#9ca3af")
        self.strength_label.setText(
            f"Strength: <b style='color: {color}'>{analysis['label']}</b> "
            f"({analysis['entropy_bits']} bits entropy)"
        )

    def _generate_password(self):
        opts = GeneratorOptions(
            length=self.len_slider.value(),
            use_uppercase=self.chk_upper.isChecked(),
            use_lowercase=self.chk_lower.isChecked(),
            use_digits=self.chk_digits.isChecked(),
            use_symbols=self.chk_symbols.isChecked(),
            exclude_ambiguous=self.chk_ambiguous.isChecked()
        )
        try:
            pw = PasswordGenerator.generate(opts)
            self.password_input.setText(pw)
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_pw_btn.setText("Hide")
        except Exception as e:
            QMessageBox.warning(self, "Generator Error", str(e))

    def _on_save(self):
        title = self.title_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not title:
            QMessageBox.warning(self, "Validation Error", "Title / Service Name is required.")
            return
        if not username:
            QMessageBox.warning(self, "Validation Error", "Username / Email is required.")
            return
        if not password:
            QMessageBox.warning(self, "Validation Error", "Password cannot be blank.")
            return

        self.accept()

    def get_data(self) -> Dict[str, str]:
        return {
            "title": self.title_input.text().strip(),
            "username": self.username_input.text().strip(),
            "password": self.password_input.text(),
            "url": self.url_input.text().strip(),
            "notes": self.notes_input.toPlainText().strip()
        }
