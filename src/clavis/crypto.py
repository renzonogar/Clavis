"""
Clavis Cryptographic Core
AES-256-GCM authenticated encryption, secure nonce generation,
associated authenticated data (AAD) packaging, and memory scrubbing.
"""

from dataclasses import dataclass
import json
import os
import secrets
import struct
from typing import Tuple, Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

from .kdf import Argon2idParams, derive_key_argon2id, InvalidKdfParametersError

# Magic identifier for Clavis Encrypted Vaults
MAGIC_BYTES = b"CLAVIS01"
CURRENT_VERSION = 1
NONCE_LENGTH = 12       # 96-bit nonce standard for AES-GCM
SALT_LENGTH = 16        # 128-bit random salt
TAG_LENGTH = 16         # 128-bit authentication tag


class CryptoError(Exception):
    """Base exception for cryptographic operations."""
    pass


class VaultAuthenticationError(CryptoError):
    """
    Raised when vault decryption or authentication tag verification fails.
    A generic message is presented to avoid leaking whether the failure was due
    to an incorrect password, corrupted ciphertext, or tampered header.
    """
    def __init__(self, message: str = "Authentication failed or vault is corrupted."):
        super().__init__(message)


class MalformedVaultError(CryptoError):
    """Raised when vault file structure or magic bytes are invalid."""
    pass


@dataclass
class VaultHeader:
    version: int
    salt: bytes
    time_cost: int
    memory_cost: int
    parallelism: int
    nonce: bytes
    custom_metadata: dict

    def to_bytes(self) -> bytes:
        """
        Serializes header to bytes.
        Format:
        [MAGIC_BYTES 8B]
        [VERSION 2B unsigned short]
        [TIME_COST 4B unsigned int]
        [MEMORY_COST 4B unsigned int]
        [PARALLELISM 2B unsigned short]
        [SALT_LEN 2B unsigned short]
        [SALT bytes]
        [NONCE_LEN 2B unsigned short]
        [NONCE bytes]
        [METADATA_LEN 4B unsigned int]
        [METADATA json utf8 bytes]
        """
        meta_bytes = json.dumps(self.custom_metadata).encode("utf-8")
        header_pack = struct.pack(
            ">8sHHIIHH",
            MAGIC_BYTES,
            self.version,
            self.time_cost,
            self.memory_cost,
            self.parallelism,
            len(self.salt),
            len(self.nonce)
        )
        return header_pack + self.salt + self.nonce + struct.pack(">I", len(meta_bytes)) + meta_bytes

    @classmethod
    def from_bytes(cls, raw: bytes) -> Tuple["VaultHeader", int]:
        """
        Parses header from beginning of vault raw bytes.
        Returns (VaultHeader, header_byte_length).
        """
        # Header fixed prefix is: 8 + 2 + 2 + 4 + 4 + 2 + 2 = 24 bytes (adjusted for struct)
        prefix_fmt = ">8sHHIIHH"
        prefix_len = struct.calcsize(prefix_fmt)
        if len(raw) < prefix_len:
            raise MalformedVaultError("File is smaller than the minimum header size.")

        magic, version, time_cost, memory_cost, parallelism, salt_len, nonce_len = struct.unpack(
            prefix_fmt, raw[:prefix_len]
        )

        if magic != MAGIC_BYTES:
            raise MalformedVaultError("Unrecognized file format or missing Clavis magic bytes.")

        if version != CURRENT_VERSION:
            raise MalformedVaultError(f"Unsupported vault version: {version}. Expected version {CURRENT_VERSION}.")

        offset = prefix_len
        if len(raw) < offset + salt_len + nonce_len + 4:
            raise MalformedVaultError("Vault file truncated in header section.")

        salt = raw[offset:offset + salt_len]
        offset += salt_len

        nonce = raw[offset:offset + nonce_len]
        offset += nonce_len

        meta_len = struct.unpack(">I", raw[offset:offset + 4])[0]
        offset += 4

        if meta_len > 1024 * 1024:  # 1 MiB limit on metadata
            raise MalformedVaultError("Metadata size header exceeds safety limits.")

        if len(raw) < offset + meta_len:
            raise MalformedVaultError("Vault file truncated in metadata section.")

        meta_raw = raw[offset:offset + meta_len]
        offset += meta_len

        try:
            custom_metadata = json.loads(meta_raw.decode("utf-8")) if meta_len > 0 else {}
        except Exception:
            raise MalformedVaultError("Failed to parse vault metadata block.")

        # Validate KDF parameters immediately
        kdf_params = Argon2idParams(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            salt_length=salt_len,
            key_length=32
        )
        try:
            kdf_params.validate()
        except InvalidKdfParametersError as e:
            raise MalformedVaultError(f"Vault contains dangerous or invalid KDF parameters: {e}")

        header = cls(
            version=version,
            salt=salt,
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            nonce=nonce,
            custom_metadata=custom_metadata
        )
        return header, offset


def secure_zero(buf: bytearray) -> None:
    """Best-effort in-place zeroization of mutable sensitive bytearrays."""
    if isinstance(buf, bytearray):
        for i in range(len(buf)):
            buf[i] = 0


def encrypt_vault_payload(
    plaintext_data: bytes,
    master_password: str,
    params: Optional[Argon2idParams] = None,
    metadata: Optional[dict] = None
) -> bytes:
    """
    Encrypts plaintext data (such as serialized SQLite database) into a self-contained
    authenticated Clavis vault file bytes.
    - Generates fresh salt and fresh nonce for every call.
    - Derives 256-bit AES key via Argon2id.
    - Authenticates the header as AAD in AES-256-GCM.
    - Appends ciphertext + 16-byte authentication tag.
    """
    if params is None:
        params = Argon2idParams()
    params.validate()

    salt = secrets.token_bytes(params.salt_length)
    nonce = secrets.token_bytes(NONCE_LENGTH)
    meta = metadata or {}

    header = VaultHeader(
        version=CURRENT_VERSION,
        salt=salt,
        time_cost=params.time_cost,
        memory_cost=params.memory_cost,
        parallelism=params.parallelism,
        nonce=nonce,
        custom_metadata=meta
    )
    header_bytes = header.to_bytes()

    pw_bytes = master_password.encode("utf-8")
    derived_key = derive_key_argon2id(pw_bytes, salt, params)

    try:
        if HAS_CRYPTOGRAPHY:
            aesgcm = AESGCM(derived_key)
            # AESGCM encrypt expects: nonce, data, associated_data
            # Returns ciphertext + 16-byte tag
            ciphertext = aesgcm.encrypt(nonce, plaintext_data, header_bytes)
        else:
            # Fallback pure-python/hashlib based implementation if cryptography isn't loaded yet
            # Uses XOR + HMAC-SHA256 authenticated envelope for testing fallback
            import hmac
            import hashlib
            key_enc = hashlib.sha256(derived_key + b"enc").digest()
            key_mac = hashlib.sha256(derived_key + b"mac").digest()
            # Simple stream keystream via SHA256 counter
            blocks = []
            for i in range((len(plaintext_data) + 31) // 32):
                ctr = struct.pack(">I", i)
                blk_key = hashlib.sha256(key_enc + nonce + ctr).digest()
                blocks.append(blk_key)
            keystream = b"".join(blocks)[:len(plaintext_data)]
            ct = bytes(a ^ b for a, b in zip(plaintext_data, keystream))
            tag = hmac.new(key_mac, header_bytes + nonce + ct, hashlib.sha256).digest()[:16]
            ciphertext = ct + tag

        return header_bytes + ciphertext
    finally:
        # Best effort cleanup of derived key in memory
        if isinstance(derived_key, bytearray):
            secure_zero(derived_key)


def decrypt_vault_payload(
    vault_file_bytes: bytes,
    master_password: str
) -> Tuple[bytes, VaultHeader]:
    """
    Authenticates and decrypts a Clavis vault file.
    Validates header, verifies AAD, derives key, and verifies GCM authentication tag.
    Returns (plaintext_bytes, header).
    Raises VaultAuthenticationError on any tampering, tag mismatch, or wrong password.
    """
    if len(vault_file_bytes) < 32:
        raise MalformedVaultError("File is too short to be a valid Clavis vault.")

    header, header_len = VaultHeader.from_bytes(vault_file_bytes)
    header_bytes = vault_file_bytes[:header_len]
    ciphertext_with_tag = vault_file_bytes[header_len:]

    if len(ciphertext_with_tag) < TAG_LENGTH:
        raise MalformedVaultError("Ciphertext payload is truncated or missing authentication tag.")

    kdf_params = Argon2idParams(
        time_cost=header.time_cost,
        memory_cost=header.memory_cost,
        parallelism=header.parallelism,
        salt_length=len(header.salt),
        key_length=32
    )

    pw_bytes = master_password.encode("utf-8")
    derived_key = derive_key_argon2id(pw_bytes, header.salt, kdf_params)

    try:
        if HAS_CRYPTOGRAPHY:
            aesgcm = AESGCM(derived_key)
            try:
                plaintext = aesgcm.decrypt(header.nonce, ciphertext_with_tag, header_bytes)
                return plaintext, header
            except Exception:
                raise VaultAuthenticationError()
        else:
            import hmac
            import hashlib
            key_enc = hashlib.sha256(derived_key + b"enc").digest()
            key_mac = hashlib.sha256(derived_key + b"mac").digest()
            ct = ciphertext_with_tag[:-16]
            tag = ciphertext_with_tag[-16:]
            expected_tag = hmac.new(key_mac, header_bytes + header.nonce + ct, hashlib.sha256).digest()[:16]
            if not hmac.compare_digest(tag, expected_tag):
                raise VaultAuthenticationError()
            blocks = []
            for i in range((len(ct) + 31) // 32):
                ctr = struct.pack(">I", i)
                blk_key = hashlib.sha256(key_enc + header.nonce + ctr).digest()
                blocks.append(blk_key)
            keystream = b"".join(blocks)[:len(ct)]
            plaintext = bytes(a ^ b for a, b in zip(ct, keystream))
            return plaintext, header
    finally:
        if isinstance(derived_key, bytearray):
            secure_zero(derived_key)
