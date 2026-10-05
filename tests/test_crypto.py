"""
Tests for Clavis Cryptographic Operations:
- AES-256-GCM encryption and decryption round trips
- Argon2id key derivation & parameter validation
- Fresh, unique nonces per operation (never reuse nonce)
- Associated Data (AAD) tamper detection
- Tampered ciphertext rejection
- Invalid tag rejection
- Generic authentication error (no leakage of reason)
- Verification that plaintext secrets are absent from ciphertext
"""

import os
import sys
import pytest

# Ensure clavis package is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from clavis.kdf import Argon2idParams, derive_key_argon2id, InvalidKdfParametersError
from clavis.crypto import (
    encrypt_vault_payload,
    decrypt_vault_payload,
    VaultHeader,
    VaultAuthenticationError,
    MalformedVaultError,
    secure_zero,
    MAGIC_BYTES,
    CURRENT_VERSION
)

# Test KDF parameters to speed up test execution
FAST_PARAMS = Argon2idParams(
    time_cost=1,
    memory_cost=4096,
    parallelism=1,
    salt_length=16,
    key_length=32
)


def test_kdf_parameter_validation():
    """Verify that dangerous or out-of-bound KDF parameters are rejected."""
    # Memory too small
    with pytest.raises(InvalidKdfParametersError):
        Argon2idParams(memory_cost=1024).validate()

    # Memory too large (DoS protection)
    with pytest.raises(InvalidKdfParametersError):
        Argon2idParams(memory_cost=1048576).validate()

    # Time cost zero
    with pytest.raises(InvalidKdfParametersError):
        Argon2idParams(time_cost=0).validate()

    # Salt too short
    with pytest.raises(InvalidKdfParametersError):
        Argon2idParams(salt_length=8).validate()

    # Valid parameters pass
    FAST_PARAMS.validate()


def test_encrypt_decrypt_roundtrip():
    """Verify clean encryption and decryption of arbitrary plaintext payloads."""
    secret_payload = b"CRITICAL_CREDENTIAL_DATA_SQLITE_PAYLOAD"
    master_password = "CorrectHorseBatteryStaple123!"

    vault_bytes = encrypt_vault_payload(
        plaintext_data=secret_payload,
        master_password=master_password,
        params=FAST_PARAMS,
        metadata={"test_key": "test_val"}
    )

    decrypted, header = decrypt_vault_payload(vault_bytes, master_password)
    assert decrypted == secret_payload
    assert header.version == CURRENT_VERSION
    assert header.custom_metadata.get("test_key") == "test_val"


def test_wrong_password_fails_generically():
    """Verify that wrong password raises VaultAuthenticationError without leaking info."""
    secret_payload = b"PRIVATE_DATA"
    correct_password = "SuperSecretPassword123!"
    wrong_password = "WrongSecretPassword123!"

    vault_bytes = encrypt_vault_payload(
        plaintext_data=secret_payload,
        master_password=correct_password,
        params=FAST_PARAMS
    )

    with pytest.raises(VaultAuthenticationError) as exc_info:
        decrypt_vault_payload(vault_bytes, wrong_password)

    # Message must be generic
    assert "Authentication failed" in str(exc_info.value)


def test_tampered_ciphertext_fails():
    """Verify that flipping a single bit in the ciphertext triggers authentication rejection."""
    secret_payload = b"VAULT_PAYLOAD_TEST"
    password = "MasterPassword456!"

    vault_bytes = bytearray(encrypt_vault_payload(secret_payload, password, params=FAST_PARAMS))

    # Tamper with the last byte of ciphertext/tag
    vault_bytes[-1] ^= 0x01

    with pytest.raises(VaultAuthenticationError):
        decrypt_vault_payload(bytes(vault_bytes), password)


def test_tampered_header_aad_fails():
    """Verify that tampering with header metadata (AAD) invalidates the GCM tag."""
    secret_payload = b"VAULT_PAYLOAD_TEST"
    password = "MasterPassword456!"

    vault_bytes = bytearray(encrypt_vault_payload(
        secret_payload,
        password,
        params=FAST_PARAMS,
        metadata={"user": "alice"}
    ))

    # Header starts after magic (8 bytes). Tamper with version or KDF fields
    vault_bytes[10] ^= 0x01

    with pytest.raises((VaultAuthenticationError, MalformedVaultError)):
        decrypt_vault_payload(bytes(vault_bytes), password)


def test_nonce_uniqueness_never_reused():
    """Verify that multiple encryptions of identical data never reuse nonces."""
    secret_payload = b"SAME_DATA"
    password = "SAME_PASSWORD"

    nonces = set()
    ciphertexts = set()

    for _ in range(15):
        vault_bytes = encrypt_vault_payload(secret_payload, password, params=FAST_PARAMS)
        header, _ = VaultHeader.from_bytes(vault_bytes)
        assert len(header.nonce) == 12
        nonces.add(header.nonce)
        ciphertexts.add(vault_bytes)

    # All 15 nonces and vault payloads must be completely distinct
    assert len(nonces) == 15
    assert len(ciphertexts) == 15


def test_no_plaintext_leakage_in_vault_bytes():
    """Verify that no sensitive plaintext string or password appears anywhere in the raw file."""
    plaintext = b"supercalifragilistic_secret_bank_pin_98765"
    password = "UncommonMasterPasswordToBeScrubbed!"

    vault_bytes = encrypt_vault_payload(plaintext, password, params=FAST_PARAMS)

    assert plaintext not in vault_bytes
    assert password.encode("utf-8") not in vault_bytes


def test_malformed_vault_headers():
    """Verify proper handling of truncated, bogus, or invalid magic files."""
    with pytest.raises(MalformedVaultError):
        decrypt_vault_payload(b"TOO_SHORT", "any")

    with pytest.raises(MalformedVaultError):
        decrypt_vault_payload(b"NOT_CLAVIS_MAGIC_BYTE_DATA_TOO_LONG_1234567890", "any")


def test_secure_zero():
    """Verify in-place zeroization of mutable bytearrays."""
    data = bytearray(b"SENSITIVE_KEY_BYTES_12345678")
    secure_zero(data)
    assert all(b == 0 for b in data)
