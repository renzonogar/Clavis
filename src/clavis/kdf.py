"""
Clavis Key Derivation Function (KDF) Module
Argon2id Key Derivation and Parameter Validation
"""

from dataclasses import dataclass
import hashlib
import os

try:
    import argon2
    import argon2.low_level as argon2_low_level
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False

# Default parameters recommended for interactive offline vault unlocks (OWASP / RFC 9106)
DEFAULT_TIME_COST = 3          # Iterations
DEFAULT_MEMORY_COST = 65536    # 64 MiB in KiB
DEFAULT_PARALLELISM = 4        # Threads / lanes
DEFAULT_SALT_LEN = 16          # 128-bit random salt
DEFAULT_KEY_LEN = 32           # 256-bit derived key for AES-256

# Bounds for safety against resource exhaustion or trivial attacks
MIN_TIME_COST = 1
MAX_TIME_COST = 100
MIN_MEMORY_COST = 4096         # 4 MiB min
MAX_MEMORY_COST = 524288       # 512 MiB max to avoid DoS/crash on constrained host
MIN_PARALLELISM = 1
MAX_PARALLELISM = 16
MIN_SALT_LEN = 16


class KdfError(Exception):
    """Base exception for Key Derivation failures."""
    pass


class InvalidKdfParametersError(KdfError):
    """Raised when KDF parameters in a vault header violate safety constraints."""
    pass


@dataclass(frozen=True)
class Argon2idParams:
    time_cost: int = DEFAULT_TIME_COST
    memory_cost: int = DEFAULT_MEMORY_COST
    parallelism: int = DEFAULT_PARALLELISM
    salt_length: int = DEFAULT_SALT_LEN
    key_length: int = DEFAULT_KEY_LEN

    def validate(self) -> None:
        """Validate parameters against resource exhaustion and minimum security levels."""
        if not (MIN_TIME_COST <= self.time_cost <= MAX_TIME_COST):
            raise InvalidKdfParametersError(
                f"Invalid time_cost {self.time_cost}: must be between {MIN_TIME_COST} and {MAX_TIME_COST}"
            )
        if not (MIN_MEMORY_COST <= self.memory_cost <= MAX_MEMORY_COST):
            raise InvalidKdfParametersError(
                f"Invalid memory_cost {self.memory_cost} KiB: must be between {MIN_MEMORY_COST} and {MAX_MEMORY_COST}"
            )
        if not (MIN_PARALLELISM <= self.parallelism <= MAX_PARALLELISM):
            raise InvalidKdfParametersError(
                f"Invalid parallelism {self.parallelism}: must be between {MIN_PARALLELISM} and {MAX_PARALLELISM}"
            )
        if self.salt_length < MIN_SALT_LEN:
            raise InvalidKdfParametersError(
                f"Salt length too short ({self.salt_length} bytes): minimum is {MIN_SALT_LEN} bytes"
            )
        if self.key_length != 32:
            raise InvalidKdfParametersError(
                f"Key length must be exactly 32 bytes for AES-256 (got {self.key_length})"
            )


def derive_key_argon2id(password: bytes, salt: bytes, params: Argon2idParams) -> bytes:
    """
    Derives a 256-bit symmetric key from a master password and salt using Argon2id.
    """
    params.validate()
    if len(salt) < params.salt_length:
        raise InvalidKdfParametersError(f"Salt provided is shorter than required {params.salt_length} bytes.")

    if HAS_ARGON2:
        return argon2_low_level.hash_secret_raw(
            secret=password,
            salt=salt,
            time_cost=params.time_cost,
            memory_cost=params.memory_cost,
            parallelism=params.parallelism,
            hash_len=params.key_length,
            type=argon2_low_level.Type.ID
        )
    else:
        # Fallback to PBKDF2-HMAC-SHA256 if argon2 C library is unavailable in the environment
        # 300,000 rounds of PBKDF2-HMAC-SHA256
        rounds = max(params.time_cost * 100000, 300000)
        return hashlib.pbkdf2_hmac(
            'sha256',
            password,
            salt,
            rounds,
            dklen=params.key_length
        )
