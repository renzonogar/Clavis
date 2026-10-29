"""KDBX vault lifecycle and explicit legacy-vault conversion."""

import os
from typing import Optional

from pykeepass.exceptions import CredentialsError

from clavis.crypto import MAGIC_BYTES, VaultAuthenticationError, MalformedVaultError
from clavis.database import VaultDatabase as LegacyVaultDatabase
from clavis.keepass_database import KeePassAuthenticationError, KeePassVaultDatabase
from clavis.storage import SafeVaultStorage, StorageError


class LegacyVaultFormatError(ValueError):
    """Raised when an older proprietary Clavis vault needs explicit conversion."""


class VaultStateError(RuntimeError):
    """Raised when an operation requires an unlocked vault."""


class ClavisVault:
    """Manage a KeePass-compatible KDBX vault stored with a .vault extension."""

    def __init__(self, path: str = ""):
        self.path = path
        self.db: Optional[KeePassVaultDatabase] = None
        self.is_unlocked = False
        self._has_unsaved_changes = False

    @property
    def vault_path(self) -> str:
        return self.path

    @property
    def has_unsaved_changes(self) -> bool:
        return self._has_unsaved_changes

    @has_unsaved_changes.setter
    def has_unsaved_changes(self, value: bool) -> None:
        self._has_unsaved_changes = bool(value)

    @classmethod
    def create_new(cls, path: str, master_password: str) -> "ClavisVault":
        if os.path.exists(path):
            raise FileExistsError(f"A file already exists at {path}.")
        vault = cls(path)
        vault.db = KeePassVaultDatabase.create(master_password)
        vault.is_unlocked = True
        try:
            vault.save()
        except Exception:
            vault.lock()
            raise
        return vault

    def open_existing(self, master_password: str) -> None:
        try:
            data = SafeVaultStorage.read_vault_bytes(self.path)
        except StorageError:
            raise

        if data.startswith(MAGIC_BYTES):
            raise LegacyVaultFormatError(
                "This is a legacy Clavis vault. Import it to a new KDBX vault first."
            )
        if len(data) < 12:
            raise MalformedVaultError("Vault file is truncated or invalid.")

        try:
            self.db = KeePassVaultDatabase.from_bytes(data, master_password)
        except KeePassAuthenticationError as error:
            raise VaultAuthenticationError(
                "Incorrect master password or invalid KDBX vault."
            ) from error
        except CredentialsError as error:
            raise VaultAuthenticationError(
                "Incorrect master password or invalid KDBX vault."
            ) from error
        except Exception as error:
            raise MalformedVaultError("Vault file is invalid or corrupted.") from error
        self.is_unlocked = True

    @classmethod
    def import_legacy(
        cls, source_path: str, destination_path: str, master_password: str
    ) -> "ClavisVault":
        """Convert a proprietary Clavis vault to KDBX without altering its source."""
        if os.path.abspath(source_path) == os.path.abspath(destination_path):
            raise ValueError("Choose a different destination to preserve the original.")
        if os.path.exists(destination_path):
            raise FileExistsError(f"A file already exists at {destination_path}.")

        legacy_bytes = SafeVaultStorage.read_vault_bytes(source_path)
        if not legacy_bytes.startswith(MAGIC_BYTES):
            raise ValueError("The selected file is not a legacy Clavis vault.")
        payload, _header = cls._decrypt_legacy(legacy_bytes, master_password)

        legacy_db = LegacyVaultDatabase()
        vault = cls(destination_path)
        try:
            legacy_db.deserialize(payload)
            vault.db = KeePassVaultDatabase.create(master_password)
            vault.is_unlocked = True
            for include_deleted in (False, True):
                credentials = legacy_db.list_credentials(
                    include_deleted=include_deleted
                )
                for credential in credentials:
                    new_id = vault.db.add_credential(
                        title=credential["title"],
                        username=credential["username"],
                        password=credential["password"],
                        url=credential.get("url", ""),
                        notes=credential.get("notes", ""),
                        is_deleted=include_deleted,
                    )
                    history = legacy_db.get_password_history(credential["id"])
                    if history:
                        vault.db.import_history(
                            new_id,
                            [item["old_password"] for item in history],
                        )
            vault.save()
        except Exception:
            vault.lock()
            raise
        finally:
            legacy_db.close()
            del payload
            del _header
        return vault

    @staticmethod
    def _decrypt_legacy(data: bytes, master_password: str):
        from clavis.crypto import decrypt_vault_payload

        return decrypt_vault_payload(data, master_password)

    def save(self, preserve_backup: bool = True):
        if not self.is_unlocked or self.db is None:
            raise VaultStateError("Cannot save a locked vault.")
        result = SafeVaultStorage.atomic_write_vault(
            self.path, self.db.serialize(), preserve_backup=preserve_backup
        )
        self._has_unsaved_changes = False
        return result

    def lock(self) -> None:
        if self.db is not None:
            self.db.close()
        self.db = None
        self.is_unlocked = False
        self._has_unsaved_changes = False

    def change_master_password(self, new_password: str) -> None:
        if not self.is_unlocked or self.db is None:
            raise VaultStateError("Cannot change password on a locked vault.")
        self.db.change_master_password(new_password)
        self._has_unsaved_changes = True
        self.save()
