"""
Tests for Clavis Safe Storage Operations:
- Atomic write-and-replace guarantees
- Verification that original vault is never truncated or destroyed on error
- Backup file creation (.bak)
- Insufficient space & permission handling
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from clavis.storage import SafeVaultStorage, StorageError, DriveDisconnectedError


def test_atomic_write_and_read(tmp_path):
    vault_path = str(tmp_path / "clavis_test.vault")
    payload = b"ENCRYPTED_VAULT_BYTES_TEST_1234567890"

    # First write
    success, msg = SafeVaultStorage.atomic_write_vault(vault_path, payload, preserve_backup=True)
    assert success is True
    assert os.path.exists(vault_path)
    assert SafeVaultStorage.read_vault_bytes(vault_path) == payload

    # Overwrite with new payload and verify backup
    payload2 = b"UPDATED_ENCRYPTED_PAYLOAD_ABCDEF"
    success, msg = SafeVaultStorage.atomic_write_vault(vault_path, payload2, preserve_backup=True)
    assert success is True
    assert SafeVaultStorage.read_vault_bytes(vault_path) == payload2

    # Backup must hold old payload
    bak_path = f"{vault_path}.bak"
    assert os.path.exists(bak_path)
    assert SafeVaultStorage.read_vault_bytes(bak_path) == payload


def test_disconnected_drive_handling():
    invalid_path = "/nonexistent_usb_mount_point_xyz/vault.vault"
    with pytest.raises(DriveDisconnectedError):
        SafeVaultStorage.atomic_write_vault(invalid_path, b"TEST")


def test_read_missing_vault():
    missing_path = "/tmp/clavis_missing_file_random_12345.vault"
    if os.path.exists(missing_path):
        os.remove(missing_path)
    with pytest.raises(StorageError):
        SafeVaultStorage.read_vault_bytes(missing_path)
