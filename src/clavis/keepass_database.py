"""In-memory adapter for KeePass KDBX databases."""

from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional
from uuid import UUID

from pykeepass import PyKeePass, create_database
from pykeepass.exceptions import CredentialsError


class KeePassAuthenticationError(ValueError):
    """Raised when KDBX authentication fails."""


class KeePassVaultDatabase:
    """Credential operations backed by a PyKeePass database held in memory."""

    def __init__(self, keepass: PyKeePass):
        self._keepass: Optional[PyKeePass] = keepass

    @classmethod
    def create(cls, master_password: str) -> "KeePassVaultDatabase":
        stream = BytesIO()
        create_database(stream, password=master_password)
        stream.seek(0)
        keepass = PyKeePass(stream, password=master_password)
        keepass._create_or_get_recyclebin_group()
        return cls(keepass)

    @classmethod
    def from_bytes(
        cls, data: bytes, master_password: str
    ) -> "KeePassVaultDatabase":
        stream = BytesIO(data)
        try:
            keepass = PyKeePass(stream, password=master_password)
            keepass._create_or_get_recyclebin_group()
            return cls(keepass)
        except CredentialsError as error:
            raise KeePassAuthenticationError(
                "Authentication failed or vault is corrupted."
            ) from error

    @property
    def keepass(self) -> PyKeePass:
        if self._keepass is None:
            raise RuntimeError("The vault database is closed.")
        return self._keepass

    @property
    def metadata(self) -> Dict[str, Any]:
        kp = self.keepass
        return {
            "version": ".".join(str(part) for part in kp.version),
            "encryption": kp.encryption_algorithm,
            "kdf": kp.kdf_algorithm,
            "name": kp.database_name,
        }

    def serialize(self) -> bytes:
        output = BytesIO()
        self.keepass.save(output)
        return output.getvalue()

    def close(self) -> None:
        self._keepass = None

    def change_master_password(self, new_password: str) -> None:
        self.keepass.password = new_password

    def add_credential(
        self,
        title: str,
        username: str,
        password: str,
        url: str = "",
        notes: str = "",
        is_deleted: bool = False,
    ) -> str:
        kp = self.keepass
        entry = kp.add_entry(kp.root_group, title.strip(), username.strip(), password)
        entry.url = url.strip()
        entry.notes = notes.strip()
        if is_deleted:
            kp.move_entry(entry, kp.recyclebin_group)
        return str(entry.uuid)

    def update_credential(
        self,
        cred_id: str,
        title: str,
        username: str,
        password: str,
        url: str = "",
        notes: str = "",
    ) -> bool:
        entry = self._find_entry(cred_id)
        if entry is None:
            return False
        if entry.password != password:
            entry.save_history()
        entry.title = title.strip()
        entry.username = username.strip()
        entry.password = password
        entry.url = url.strip()
        entry.notes = notes.strip()
        entry.touch(modify=True)
        return True

    def soft_delete_credential(self, cred_id: str) -> bool:
        entry = self._find_entry(cred_id)
        if entry is None or self._is_deleted(entry):
            return False
        self.keepass.move_entry(entry, self.keepass.recyclebin_group)
        return True

    def restore_credential(self, cred_id: str) -> bool:
        entry = self._find_entry(cred_id)
        if entry is None or not self._is_deleted(entry):
            return False
        self.keepass.move_entry(entry, self.keepass.root_group)
        return True

    def permanently_delete_credential(self, cred_id: str) -> bool:
        entry = self._find_entry(cred_id)
        if entry is None:
            return False
        self.keepass.delete_entry(entry)
        return True

    def empty_trash(self) -> int:
        entries = list(self.keepass.recyclebin_group.entries)
        for entry in entries:
            self.keepass.delete_entry(entry)
        return len(entries)

    def get_credential(self, cred_id: str) -> Optional[Dict[str, Any]]:
        entry = self._find_entry(cred_id)
        return self._to_credential(entry) if entry is not None else None

    def list_credentials(
        self,
        include_deleted: bool = False,
        search_query: str = "",
        sort_by: str = "title",
    ) -> List[Dict[str, Any]]:
        query = search_query.strip().casefold()
        results = []
        for entry in self.keepass.entries:
            is_deleted = self._is_deleted(entry)
            if is_deleted != include_deleted:
                continue
            credential = self._to_credential(entry)
            if query and not any(
                query in str(credential.get(key) or "").casefold()
                for key in ("title", "username", "url", "notes")
            ):
                continue
            results.append(credential)

        sort_keys = {
            "title": lambda item: item["title"].casefold(),
            "title_desc": lambda item: item["title"].casefold(),
            "updated_at": lambda item: item["updated_at"],
            "created_at": lambda item: item["created_at"],
        }
        results.sort(
            key=sort_keys.get(sort_by, sort_keys["title"]),
            reverse=sort_by in ("title_desc", "updated_at", "created_at"),
        )
        return results

    def get_password_history(self, cred_id: str) -> List[Dict[str, Any]]:
        entry = self._find_entry(cred_id)
        if entry is None:
            return []
        history = []
        for old_entry in reversed(entry.history):
            changed_at = old_entry.ctime
            history.append({
                "id": str(old_entry.uuid),
                "credential_id": cred_id,
                "old_password": old_entry.password or "",
                "changed_at": int(changed_at.timestamp()) if changed_at else 0,
            })
        return sorted(history, key=lambda item: item["changed_at"], reverse=True)

    def clear_password_history(self, cred_id: Optional[str] = None) -> int:
        entries = (
            [self._find_entry(cred_id)]
            if cred_id
            else list(self.keepass.entries)
        )
        cleared = 0
        for entry in entries:
            if entry is None:
                continue
            history = list(entry.history)
            if history:
                entry.delete_history()
                cleared += len(history)
        return cleared

    def import_history(self, cred_id: str, old_passwords: List[str]) -> None:
        entry = self._find_entry(cred_id)
        if entry is None:
            raise KeyError(f"Credential {cred_id} not found.")
        current_password = entry.password
        for password in reversed(old_passwords):
            entry.password = password
            entry.save_history()
        entry.password = current_password

    def _find_entry(self, cred_id: str):
        try:
            target_uuid = UUID(cred_id)
        except (ValueError, TypeError, AttributeError):
            return None
        return next(
            (entry for entry in self.keepass.entries if entry.uuid == target_uuid),
            None,
        )

    def _is_deleted(self, entry) -> bool:
        recycle_bin = self.keepass.recyclebin_group
        return recycle_bin is not None and entry.group.uuid == recycle_bin.uuid

    @staticmethod
    def _timestamp(value: Optional[datetime]) -> int:
        if value is None:
            return 0
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp())

    def _to_credential(self, entry) -> Dict[str, Any]:
        return {
            "id": str(entry.uuid),
            "title": entry.title or "",
            "username": entry.username or "",
            "password": entry.password or "",
            "url": entry.url or "",
            "notes": entry.notes or "",
            "created_at": self._timestamp(entry.ctime),
            "updated_at": self._timestamp(entry.mtime),
            "is_deleted": self._is_deleted(entry),
            "deleted_at": None,
        }
