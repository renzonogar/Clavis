"""Vault lifecycle, KeePass interoperability, and legacy conversion tests."""

import os
import sys
from io import BytesIO

import pytest
from pykeepass import PyKeePass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from clavis.crypto import Argon2idParams, MAGIC_BYTES, encrypt_vault_payload
from clavis.database import VaultDatabase
from clavis.vault import (
    ClavisVault,
    LegacyVaultFormatError,
    VaultAuthenticationError,
    VaultStateError,
    MalformedVaultError,
)


PASSWORD = "StrongVaultMasterKey#987"


def test_vault_create_reopen_and_open_in_keepass(tmp_path):
    vault_path = str(tmp_path / "passwords.vault")
    vault = ClavisVault.create_new(vault_path, PASSWORD)
    first = vault.db.add_credential(
        "ProtonMail", "alice@proton.me", "Mail-secret-92",
        url="https://proton.me", notes="Primary email",
    )
    second = vault.db.add_credential(
        "GitHub", "alice_dev", "Git-secret-58", url="https://github.com"
    )
    vault.save()
    vault.lock()

    raw = open(vault_path, "rb").read()
    assert not raw.startswith(MAGIC_BYTES)
    keepass = PyKeePass(BytesIO(raw), password=PASSWORD)
    assert {entry.title for entry in keepass.entries} >= {"ProtonMail", "GitHub"}

    reopened = ClavisVault(vault_path)
    reopened.open_existing(PASSWORD)
    credentials = reopened.db.list_credentials()
    assert {credential["id"] for credential in credentials} == {first, second}
    assert {credential["title"] for credential in credentials} == {"ProtonMail", "GitHub"}

    with pytest.raises(VaultAuthenticationError):
        ClavisVault(vault_path).open_existing("WrongPassword123!")


def test_locked_vault_cannot_be_saved(tmp_path):
    vault = ClavisVault.create_new(str(tmp_path / "locked.vault"), PASSWORD)
    vault.lock()
    with pytest.raises(VaultStateError):
        vault.save()


def test_master_password_change_reencrypts_kdbx(tmp_path):
    path = str(tmp_path / "password-change.vault")
    vault = ClavisVault.create_new(path, PASSWORD)
    vault.db.add_credential("Example", "user", "Example-secret-83")
    vault.change_master_password("Another-Strong-Master-Password-7!")
    with pytest.raises(VaultAuthenticationError):
        ClavisVault(path).open_existing(PASSWORD)
    reopened = ClavisVault(path)
    reopened.open_existing("Another-Strong-Master-Password-7!")
    assert len(reopened.db.list_credentials()) == 1


def test_open_rejects_malformed_kdbx(tmp_path):
    path = tmp_path / "invalid.vault"
    path.write_bytes(b"not a KDBX database")
    with pytest.raises(MalformedVaultError):
        ClavisVault(str(path)).open_existing(PASSWORD)


def test_password_history_is_preserved_in_order(tmp_path):
    vault = ClavisVault.create_new(str(tmp_path / "history.vault"), PASSWORD)
    credential_id = vault.db.add_credential("Bank", "user", "OldPassword1")
    vault.db.update_credential(credential_id, "Bank", "user", "NewPassword2")
    vault.db.update_credential(credential_id, "Bank", "user", "NewPassword3")
    history = vault.db.get_password_history(credential_id)
    assert [item["old_password"] for item in history] == [
        "NewPassword2", "OldPassword1",
    ]


def test_trash_restore_delete_and_empty(tmp_path):
    vault = ClavisVault.create_new(str(tmp_path / "trash.vault"), PASSWORD)
    first = vault.db.add_credential("Item 1", "u1", "p1")
    second = vault.db.add_credential("Item 2", "u2", "p2")
    third = vault.db.add_credential("Item 3", "u3", "p3")

    assert len(vault.db.list_credentials()) == 3
    assert vault.db.soft_delete_credential(first)
    assert [item["id"] for item in vault.db.list_credentials(include_deleted=True)] == [first]
    assert vault.db.restore_credential(first)
    assert len(vault.db.list_credentials()) == 3
    assert vault.db.soft_delete_credential(second)
    assert vault.db.permanently_delete_credential(second)
    assert vault.db.get_credential(second) is None
    assert vault.db.soft_delete_credential(third)
    assert vault.db.empty_trash() == 1
    assert vault.db.list_credentials(include_deleted=True) == []


def test_search_covers_title_username_url_and_notes(tmp_path):
    vault = ClavisVault.create_new(str(tmp_path / "search.vault"), PASSWORD)
    vault.db.add_credential("GitLab", "john_gitlab", "pw1", url="https://gitlab.com")
    vault.db.add_credential("DigitalOcean", "john_do", "pw2", notes="API access token")
    vault.db.add_credential("Twitter", "john_tweet", "pw3")
    for query in ("gitlab", "john_do", "token", "gitlab.com"):
        assert len(vault.db.list_credentials(search_query=query)) == 1
    assert vault.db.list_credentials(search_query="not-found") == []


def test_legacy_import_preserves_original_and_converts_entries(tmp_path):
    legacy_path = str(tmp_path / "old.vault")
    converted_path = str(tmp_path / "converted.vault")
    legacy_db = VaultDatabase()
    credential_id = legacy_db.add_credential(
        "Old service", "legacy-user", "Old-secret-64",
        url="https://example.test", notes="retained",
    )
    legacy_db.update_credential(
        credential_id, "Old service", "legacy-user", "Current-secret-72",
        url="https://example.test", notes="retained",
    )
    deleted_id = legacy_db.add_credential("Deleted", "old-user", "trash-secret-73")
    legacy_db.soft_delete_credential(deleted_id)
    legacy_bytes = encrypt_vault_payload(
        legacy_db.serialize(),
        PASSWORD,
        Argon2idParams(time_cost=1, memory_cost=4096, parallelism=1),
    )
    with open(legacy_path, "wb") as file:
        file.write(legacy_bytes)
    original = open(legacy_path, "rb").read()

    with pytest.raises(LegacyVaultFormatError):
        ClavisVault(legacy_path).open_existing(PASSWORD)

    converted = ClavisVault.import_legacy(legacy_path, converted_path, PASSWORD)
    assert open(legacy_path, "rb").read() == original
    imported = converted.db.get_credential(
        converted.db.list_credentials()[0]["id"]
    )
    assert imported["title"] == "Old service"
    assert imported["username"] == "legacy-user"
    assert imported["url"] == "https://example.test"
    assert imported["notes"] == "retained"
    assert imported["password"] == "Current-secret-72"
    history = converted.db.get_password_history(imported["id"])
    assert [item["old_password"] for item in history] == ["Old-secret-64"]
    assert len(converted.db.list_credentials(include_deleted=True)) == 1
    converted.lock()

    reopened = ClavisVault(converted_path)
    reopened.open_existing(PASSWORD)
    assert reopened.db.get_credential(credential_id) is None
    assert len(reopened.db.list_credentials()) == 1
    assert len(reopened.db.list_credentials(include_deleted=True)) == 1


def test_create_does_not_overwrite_existing_file(tmp_path):
    path = tmp_path / "existing.vault"
    path.write_bytes(b"keep this file")
    with pytest.raises(FileExistsError):
        ClavisVault.create_new(str(path), PASSWORD)
    assert path.read_bytes() == b"keep this file"
