"""
Clavis Settings View (PySide6)
Configuration for inactivity timeouts, generator defaults, master password change,
vault technical inspection, and transparent security disclosures.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFrame, QScrollArea, QMessageBox, QLineEdit
)

from ..vault import ClavisVault


class SettingsView(QWidget):
    """Settings view for configuring security preferences and inspecting vault parameters."""

    timeout_changed = Signal(int)
    master_password_change_requested = Signal(str)

    def __init__(self, vault: ClavisVault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(20)
        layout.setContentsMargins(32, 32, 32, 32)

        # Inactivity Timeout Section
        timeout_box, timeout_layout = self._create_section("SESSION SECURITY & INACTIVITY TIMEOUT")

        t_row = QHBoxLayout()
        t_label = QLabel("Lock vault automatically after inactivity:")
        t_label.setStyleSheet("color: #e5e7eb; font-size: 13px;")

        self.timeout_combo = QComboBox()
        self.timeout_combo.setStyleSheet("background-color: #121316; color: #f3f4f6; border: 1px solid #374151; padding: 6px 12px; border-radius: 6px;")
        self.timeout_combo.addItem("1 Minute", 60)
        self.timeout_combo.addItem("5 Minutes (Recommended)", 300)
        self.timeout_combo.addItem("15 Minutes", 900)
        self.timeout_combo.addItem("30 Minutes", 1800)
        self.timeout_combo.addItem("Never (High Risk)", 0)
        self.timeout_combo.setCurrentIndex(1)  # Default 5 min
        self.timeout_combo.currentIndexChanged.connect(self._on_timeout_changed)

        t_row.addWidget(t_label)
        t_row.addStretch()
        t_row.addWidget(self.timeout_combo)
        timeout_layout.addLayout(t_row)
        layout.addWidget(timeout_box)

        # Master Password Change Section
        pw_box, pw_layout = self._create_section("CHANGE MASTER PASSWORD")
        pw_layout.setSpacing(10)

        pw_info = QLabel("Re-encrypts the entire vault with a newly derived 256-bit key upon next save.")
        pw_info.setStyleSheet("color: #9ca3af; font-size: 12px;")
        pw_layout.addWidget(pw_info)

        pw_row1 = QHBoxLayout()
        self.new_pw_input = QLineEdit()
        self.new_pw_input.setPlaceholderText("New master password (min 16 chars recommended)")
        self.new_pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_pw_input.setStyleSheet("background-color: #121316; color: #f3f4f6; border: 1px solid #374151; padding: 8px; border-radius: 6px;")

        self.apply_pw_btn = QPushButton("Change Password")
        self.apply_pw_btn.setStyleSheet("background-color: #4f46e5; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 600;")
        self.apply_pw_btn.clicked.connect(self._on_change_password)

        pw_row1.addWidget(self.new_pw_input, 1)
        pw_row1.addWidget(self.apply_pw_btn)
        pw_layout.addLayout(pw_row1)
        layout.addWidget(pw_box)

        # Vault Technical Parameters
        info_box, info_layout = self._create_section("CRYPTOGRAPHIC & VAULT PARAMETERS")
        info_layout.setSpacing(8)

        v_path = self.vault.vault_path or "Unknown"
        header = self.vault.header
        time_cost = header.time_cost if header else 3
        memory_cost = (header.memory_cost // 1024) if header else 64
        parallelism = header.parallelism if header else 4

        info_items = [
            ("Vault Path:", v_path),
            ("Symmetric Cipher:", "AES-256-GCM (Authenticated Encryption, 96-bit fresh nonce per write)"),
            ("Key Derivation:", f"Argon2id (time={time_cost}, memory={memory_cost}MiB, threads={parallelism})"),
            ("Salt Length:", "128 bits (16 bytes, cryptographically random)"),
            ("In-Memory Store:", "SQLite :memory: transient database (no plaintext persisted to disk)"),
            ("Atomic Save:", "Temporary file flush -> fsync -> atomic POSIX/NT replace")
        ]

        for k, v in info_items:
            row = QHBoxLayout()
            kl = QLabel(k)
            kl.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 600;")
            kl.setFixedWidth(140)
            vl = QLabel(str(v))
            vl.setStyleSheet("color: #e5e7eb; font-size: 12px;")
            vl.setWordWrap(True)
            row.addWidget(kl)
            row.addWidget(vl, 1)
            info_layout.addLayout(row)

        layout.addWidget(info_box)

        # Transparent Threat Model & Security Disclosures
        disclaimer_box, disc_layout = self._create_section("SECURITY ARCHITECTURE & THREAT MODEL")
        disc_layout.setSpacing(10)

        disclosures = [
            ("Offline-First Boundary:",
             "Clavis contains zero telemetry, zero analytics, zero cloud synchronizations, and zero remote network calls. "
             "All encryption, decryption, and credential processing happens entirely on your local machine."),
            ("Physical USB Storage:",
             "Keeping the vault file on a physical USB drive drastically reduces remote exposure. However, the host operating system "
             "manages RAM, pagefiles/swap, crash dumps, and USB bus communication. A compromised host with malware or keyloggers "
             "can intercept credentials while the vault is unlocked."),
            ("Flash Storage & Wear Leveling:",
             "Flash drives (NAND flash) use internal wear-leveling controllers. Logical deletion or file overwrites cannot guarantee "
             "instant physical eradication of old flash blocks. Keep the entire USB drive secure."),
            ("No Backdoor:",
             "There is no master override, escrow key, or recovery mechanism. If the master password is lost, data is permanently inaccessible.")
        ]

        for title, text in disclosures:
            tl = QLabel(title)
            tl.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 600;")
            txt = QLabel(text)
            txt.setWordWrap(True)
            txt.setStyleSheet("color: #9ca3af; font-size: 12px; line-height: 1.4;")
            disc_layout.addWidget(tl)
            disc_layout.addWidget(txt)

        layout.addWidget(disclaimer_box)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _create_section(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1a1c23;
                border: 1px solid #2a2d39;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        lbl = QLabel(title)
        lbl.setStyleSheet("color: #d1d5db; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 6px;")
        layout = QVBoxLayout(frame)
        layout.addWidget(lbl)
        return frame, layout

    def _on_timeout_changed(self, idx: int):
        secs = self.timeout_combo.itemData(idx)
        self.timeout_changed.emit(secs)

    def _on_change_password(self):
        new_pw = self.new_pw_input.text()
        if not new_pw or len(new_pw) < 8:
            QMessageBox.warning(self, "Invalid Password", "Master password must be at least 8 characters long.")
            return

        self.master_password_change_requested.emit(new_pw)
        self.new_pw_input.clear()
        QMessageBox.information(
            self,
            "Password Changed",
            "Master password updated for this session. Remember to save the vault to commit changes."
        )
