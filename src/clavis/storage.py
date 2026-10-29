"""
Clavis Storage Layer
Safe atomic file replacement, flash storage sync, and backup management.
Guarantees that an existing valid vault is never deleted or truncated until
the new encrypted vault file is fully written, flushed, and verified.
"""

import errno
import os
import secrets
import shutil
from typing import Optional, Tuple


class StorageError(Exception):
    """Base exception for storage and file operations."""
    pass


class InsufficientSpaceError(StorageError):
    """Raised when the target drive runs out of disk space."""
    pass


class DriveDisconnectedError(StorageError):
    """Raised when the target drive or USB device is disconnected/inaccessible."""
    pass


class SafeVaultStorage:
    """
    Handles persistence of encrypted vault files to physical or removable media.
    Follows atomic write-and-replace patterns with fsync flushing and backup preservation.
    """

    @staticmethod
    def check_drive_accessible(path: str) -> bool:
        """Checks if directory of the path is accessible and writable."""
        dirname = os.path.dirname(os.path.abspath(path))
        if not os.path.exists(dirname):
            return False
        return os.access(dirname, os.W_OK)

    @staticmethod
    def get_available_space(path: str) -> int:
        """Returns free space in bytes on the filesystem hosting path."""
        dirname = os.path.dirname(os.path.abspath(path))
        if not os.path.exists(dirname):
            raise DriveDisconnectedError(f"Directory {dirname} is not accessible.")
        return shutil.disk_usage(dirname).free

    @classmethod
    def atomic_write_vault(
        cls,
        target_path: str,
        vault_bytes: bytes,
        preserve_backup: bool = True
    ) -> Tuple[bool, str]:
        """
        Safely writes encrypted vault bytes to target_path:
        1. Confirms target directory exists and is accessible.
        2. Checks available disk space.
        3. Writes payload to a temporary file in the same directory.
        4. Issues fsync to guarantee flash/disk write completion.
        5. Preserves existing vault as .bak if requested.
        6. Atomically replaces destination with temp file using os.replace.
        """
        target_path = os.path.abspath(target_path)
        target_dir = os.path.dirname(target_path)

        if not os.path.exists(target_dir):
            raise DriveDisconnectedError(f"Target directory '{target_dir}' does not exist or device was removed.")

        # Ensure directory is writable
        if not os.access(target_dir, os.W_OK):
            raise StorageError(f"Target directory '{target_dir}' is not writable. Check USB mount permissions.")

        # Check required space (need at least 2x size of payload for safe replacement)
        try:
            free_bytes = cls.get_available_space(target_path)
            required_bytes = len(vault_bytes) * 2 + (1024 * 1024)  # Safety margin
            if free_bytes < required_bytes:
                raise InsufficientSpaceError(
                    f"Insufficient space on drive: {free_bytes} bytes available, {required_bytes} needed for atomic save."
                )
        except (OSError, DriveDisconnectedError) as e:
            if isinstance(e, InsufficientSpaceError):
                raise
            raise DriveDisconnectedError(f"Failed to check drive accessibility: {e}")

        # Unique temp file in the SAME filesystem to allow atomic rename
        rand_suffix = secrets.token_hex(6)
        temp_path = f"{target_path}.tmp.{rand_suffix}"
        backup_path = f"{target_path}.bak"

        try:
            # Open with write, exclusive flags where possible
            binary_flag = getattr(os, "O_BINARY", 0)
            fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | binary_flag, 0o600)
            try:
                total_written = 0
                while total_written < len(vault_bytes):
                    written = os.write(fd, vault_bytes[total_written:])
                    if written == 0:
                        raise StorageError("Write stalled: zero bytes written.")
                    total_written += written

                # Force write through OS buffers to hardware flash/disk controller
                os.fsync(fd)
            finally:
                os.close(fd)

            # Verify size of written temporary file
            actual_size = os.path.getsize(temp_path)
            if actual_size != len(vault_bytes):
                raise StorageError(f"Integrity check failed: wrote {actual_size} bytes, expected {len(vault_bytes)}.")

            # Create backup of existing vault if one exists
            if preserve_backup and os.path.exists(target_path):
                try:
                    shutil.copy2(target_path, backup_path)
                except OSError as backup_error:
                    raise StorageError(
                        f"Could not preserve the existing vault backup at '{backup_path}'."
                    ) from backup_error

            # Atomic replace (POSIX atomic; Windows replaces atomically on NT 4.0+)
            os.replace(temp_path, target_path)

            return True, f"Vault safely persisted ({actual_size} bytes)"

        except OSError as oe:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

            if oe.errno == errno.ENOSPC:
                raise InsufficientSpaceError("Disk is full (ENOSPC). Vault save aborted without modifying existing file.")
            elif oe.errno in (errno.ENOENT, errno.EIO, errno.ENODEV):
                raise DriveDisconnectedError(f"I/O or device disconnection error: {oe}")
            else:
                raise StorageError(f"Failed to safely persist vault file: {oe}")

        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise StorageError(f"Unexpected error during atomic vault save: {e}")

    @classmethod
    def read_vault_bytes(cls, path: str) -> bytes:
        """Reads encrypted vault file bytes from media."""
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise StorageError(f"Vault file not found at '{path}'. Check if the USB drive is connected.")

        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError as e:
            raise StorageError(f"Failed to read vault file from media: {e}")
