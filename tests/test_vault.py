"""
Tests for Clavis Vault Operations:
- In-memory SQLite lifecycle
- Vault creation and reopening round trips
- Credential CRUD operations
- Password history logging on credential edit
- Soft delete, trash listing, restore, permanent deletion, empty trash
- Search querying
- Vault lock wipes in-memory references
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from clavis.vault import ClavisVault, VaultAuthenticationError, VaultStateError
from clavis.kdf import Argon2idParams

FAST_PARAMS = Argon2idParams(
    time_cost=1,
    memory_cost=4096,
    parallelism=1,
    salt_length=16,
    key_length=32
)


def test_vault_create_and_reopen(tmp_path):
    vault_file = str(tmp_path / "test_usb_drive" / "passwords.vault")
    os.makedirs(os.path.dirname(vault_file), exist_ok=True)
    master_pw = "StrongVaultMasterKey#987"

    # 1. Create Vault
    vault = ClavisVault.create_new(
        vault_path=vault_file,
        master_password=master_pw,
        kdf_params=FAST_PARAMS,
        auxiliary_usb_uuid="USB-TEST-UUID-1234"
    )
    assert vault.is_unlocked is True
    assert vault.db is not None
    assert os.path.exists(vault_file)

    # 2. Add Credentials
    cred1_id = vault.db.add_credential(
        title="ProtonMail",
        username="alice@proton.me",
        password="PassWord#123",
        url="https://proton.me",
        notes="Primary email"
    )
    assert cred1_id is not None

    cred2_id = vault.db.add_credential(
        title="GitHub",
        username="alice_dev",
        password="GitHubSecret#456",
        url="https://github.com"
    )
    assert cred2_id is not None

    # 3. Save to disk/USB
    vault.save()

    # 4. Lock vault
    vault.lock()
    assert vault.is_unlocked is False
    assert vault.db is None

    # Operations should fail when locked
    with pytest.raises(VaultStateError):
        vault.save()

    # 5. Reopen with correct password
    reopened = ClavisVault(vault_file)
    reopened.open_existing(master_pw)
    assert reopened.is_unlocked is True
    assert reopened.db is not None

    creds = reopened.db.list_credentials()
    assert len(creds) == 2
    titles = [c["title"] for c in creds]
    assert "ProtonMail" in titles
    assert "GitHub" in titles

    # 6. Reopen with wrong password must fail
    fail_vault = ClavisVault(vault_file)
    with pytest.raises(VaultAuthenticationError):
        fail_vault.open_existing("WrongPassword123!")


def test_credential_history_and_updates(tmp_path):
    vault_file = str(tmp_path / "hist.vault")
    vault = ClavisVault.create_new(vault_file, "MasterKey123456!", kdf_params=FAST_PARAMS)

    cred_id = vault.db.add_credential("Bank", "user", "OldPassword1")
    hist = vault.db.get_password_history(cred_id)
    assert len(hist) == 0

    # Update title and username only - password unchanged
    vault.db.update_credential(cred_id, "Bank Corporate", "user2", "OldPassword1")
    assert len(vault.db.get_password_history(cred_id)) == 0

    # Update password - old password should be stored in history
    vault.db.update_credential(cred_id, "Bank Corporate", "user2", "NewPassword2")
    hist = vault.db.get_password_history(cred_id)
    assert len(hist) == 1
    assert hist[0]["old_password"] == "OldPassword1"

    # Update password again
    vault.db.update_credential(cred_id, "Bank Corporate", "user2", "NewPassword3")
    hist = vault.db.get_password_history(cred_id)
    assert len(hist) == 2
    assert hist[0]["old_password"] == "NewPassword2"
    assert hist[1]["old_password"] == "OldPassword1"


def test_soft_delete_and_trash_workflow(tmp_path):
    vault_file = str(tmp_path / "trash.vault")
    vault = ClavisVault.create_new(vault_file, "MasterKey123456!", kdf_params=FAST_PARAMS)

    id1 = vault.db.add_credential("Item 1", "u1", "p1")
    id2 = vault.db.add_credential("Item 2", "u2", "p2")
    id3 = vault.db.add_credential("Item 3", "u3", "p3")

    assert len(vault.db.list_credentials(include_deleted=False)) == 3
    assert len(vault.db.list_credentials(include_deleted=True)) == 0

    # Soft delete item 1
    vault.db.soft_delete_credential(id1)
    active = vault.db.list_credentials(include_deleted=False)
    trash = vault.db.list_credentials(include_deleted=True)

    assert len(active) == 2
    assert len(trash) == 1
    assert trash[0]["id"] == id1

    # Restore item 1
    vault.db.restore_credential(id1)
    assert len(vault.db.list_credentials(include_deleted=False)) == 3
    assert len(vault.db.list_credentials(include_deleted=True)) == 0

    # Soft delete item 2 and permanently delete it
    vault.db.soft_delete_credential(id2)
    vault.db.permanently_delete_credential(id2)
    assert len(vault.db.list_credentials(include_deleted=False)) == 2
    assert len(vault.db.list_credentials(include_deleted=True)) == 0
    assert vault.db.get_credential(id2) is None

    # Empty trash
    vault.db.soft_delete_credential(id3)
    assert len(vault.db.list_credentials(include_deleted=True)) == 1
    purged = vault.db.empty_trash()
    assert purged == 1
    assert len(vault.db.list_credentials(include_deleted=True)) == 0


def test_credential_search(tmp_path):
    vault_file = str(tmp_path / "search.vault")
    vault = ClavisVault.create_new(vault_file, "MasterKey123456!", kdf_params=FAST_PARAMS)

    vault.db.add_credential("GitLab", "john_gitlab", "pw1", url="https://gitlab.com")
    vault.db.add_credential("DigitalOcean", "john_do", "pw2", notes="API access token inside")
    vault.db.add_credential("Twitter", "john_tweet", "pw3")

    # Search title
    assert len(vault.db.list_credentials(search_query="gitlab")) == 1
    # Search username
    assert len(vault.db.list_credentials(search_query="john_do")) == 1
    # Search notes
    assert len(vault.db.list_credentials(search_query="token")) == 1
    # Search url
    assert len(vault.db.list_credentials(search_query="gitlab.com")) == 1
    # No match
    assert len(vault.db.list_credentials(search_query="nonexistent")) == 0
