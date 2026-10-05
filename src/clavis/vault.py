"""
Clavis Vault Controller
Orchestrates vault lifecycle: creation, opening, authentication, in-memory SQLite,
safe persistence, atomic backup, and secure teardown.
"""

from dataclasses import dataclass
import os
import secrets
from typing import Optional, Dict, Any, List, Tuple

from .kdf import Argon2idParams
from .crypto import (
    encrypt_vault_payload,
    decrypt_vault_payload,
    VaultHeader,
    VaultAuthenticationError,
    MalformedVaultError,
    CURRENT_VERSION
)
from .database import VaultDatabase
from .storage import SafeVaultStorage, StorageError, InsufficientSpaceError, DriveDisconnectedError
from .usb import UsbManager


class VaultStateError(Exception):
    """Raised when an operation is performed in an invalid vault state."""
    pass


class ClavisVault:
    """
    Primary Clavis Vault Controller instance.
    Controls the lifecycle of a single encrypted vault.
    """
    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path: Optional[str] = os.path.abspath(vault_path) if vault_path else None
        self.db: Optional[VaultDatabase] = None
        self.header: Optional[VaultHeader] = None
        self._master_password: Optional[str] = None
        self.is_unlocked: bool = False
        self.has_unsaved_changes: bool = False
        self.auxiliary_usb_uuid: Optional[str] = None

    @classmethod
    def create_new(
        cls,
        vault_path: str,
        master_password: str,
        kdf_params: Optional[Argon2idParams] = None,
        auxiliary_usb_uuid: Optional[str] = None
    ) -> "ClavisVault":
        """
        Creates a new encrypted vault at vault_path.
        Initializes an in-memory SQLite database, encrypts it, and writes to media.
        """
        if not master_password or len(master_password) < 8:
            raise ValueError("Master password must be at least 8 characters long.")

        vault = cls(vault_path=vault_path)
        vault.db = VaultDatabase()
        vault._master_password = master_password
        vault.auxiliary_usb_uuid = auxiliary_usb_uuid

        # Store vault metadata
        vault.db.set_setting("created_at_version", str(CURRENT_VERSION))
        if auxiliary_usb_uuid:
            vault.db.set_setting("auxiliary_usb_uuid", auxiliary_usb_uuid)

        # Serialize in-memory DB and encrypt
        db_bytes = vault.db.serialize()
        meta = {"aux_device_uuid": auxiliary_usb_uuid} if auxiliary_usb_uuid else {}
        encrypted_bytes = encrypt_vault_payload(
            plaintext_data=db_bytes,
            master_password=master_password,
            params=kdf_params,
            metadata=meta
        )

        # Write to USB/disk atomically
        SafeVaultStorage.atomic_write_vault(vault_path, encrypted_bytes, preserve_backup=False)

        vault.is_unlocked = True
        vault.has_unsaved_changes = False
        return vault

    def open_existing(self, master_password: str) -> None:
        """
        Reads encrypted vault from media, verifies authentication tag,
        and reconstructs the in-memory SQLite database.
        """
        if not self.vault_path:
            raise VaultStateError("No vault path specified.")

        raw_bytes = SafeVaultStorage.read_vault_bytes(self.vault_path)
        plaintext_db_bytes, header = decrypt_vault_payload(raw_bytes, master_password)

        # Initialize in-memory database
        self.db = VaultDatabase()
        self.db.deserialize(plaintext_db_bytes)

        self.header = header
        self._master_password = master_password
        self.is_unlocked = True
        self.has_unsaved_changes = False
        self.auxiliary_usb_uuid = header.custom_metadata.get("aux_device_uuid")

    def save(self, preserve_backup: bool = True) -> Tuple[bool, str]:
        """
        Encrypts current in-memory database and commits to physical storage safely.
        """
        if not self.is_unlocked or not self.db or not self._master_password:
            raise VaultStateError("Vault is locked or not initialized.")

        if not self.vault_path:
            raise VaultStateError("Vault path is unset.")

        # Verify USB/path is still connected before attempting save
        target_dir = os.path.dirname(self.vault_path)
        if not SafeVaultStorage.check_drive_accessible(self.vault_path):
            raise DriveDisconnectedError(
                f"Storage media at '{target_dir}' is inaccessible. Did you disconnect the USB drive? "
                "Write aborted to prevent unauthorized redirect to host disk."
            )

        db_bytes = self.db.serialize()
        meta = {"aux_device_uuid": self.auxiliary_usb_uuid} if self.auxiliary_usb_uuid else {}

        # Use same KDF params as original or defaults
        params = None
        if self.header:
            params = Argon2idParams(
                time_cost=self.header.time_cost,
                memory_cost=self.header.memory_cost,
                parallelism=self.header.parallelism,
                salt_length=len(self.header.salt)
            )

        # Fresh nonce and salt generated internally on every encrypt call
        encrypted_bytes = encrypt_vault_payload(
            plaintext_data=db_bytes,
            master_password=self._master_password,
            params=params,
            metadata=meta
        )

        success, msg = SafeVaultStorage.atomic_write_vault(
            self.vault_path,
            encrypted_bytes,
            preserve_backup=preserve_backup
        )
        self.has_unsaved_changes = False
        return success, msg

    def lock(self) -> None:
        """
        Locks the vault: closes the in-memory database, nullifies password references,
        and releases transient memory.
        """
        if self.db:
            self.db.close()
            self.db = None

        self._master_password = None
        self.is_unlocked = False
        self.has_unsaved_changes = False
        self.header = None

    def change_master_password(self, new_password: str) -> None:
        """
        Updates the master password for the active session.
        Will re-encrypt on next save.
        """
        if not self.is_unlocked:
            raise VaultStateError("Cannot change password while vault is locked.")
        if not new_password or len(new_password) < 8:
            raise ValueError("Master password must be at least 8 characters long.")

        self._master_password = new_password
        self.has_unsaved_changes = True
