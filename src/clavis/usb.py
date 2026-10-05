"""
Clavis USB and Removable Media Detection Module
Handles portable identification of removable drives, volume mount points,
auxiliary UUID / serial verification, and disconnect monitoring.

SECURITY NOTICE:
A USB UUID or volume serial number is used strictly as an auxiliary device check
for user convenience. It is NOT secret, can be cloned or spoofed, and MUST NEVER
be treated as a second-factor authentication mechanism.
"""

from dataclasses import dataclass
import os
import platform
import subprocess
import sys
from typing import List, Optional


@dataclass
class UsbDevice:
    device_id: str
    mount_point: str
    label: str
    filesystem: str
    total_bytes: int
    free_bytes: int
    is_removable: bool
    uuid: Optional[str] = None

    @property
    def display_name(self) -> str:
        name = self.label or "Removable USB Drive"
        size_gb = self.total_bytes / (1024 ** 3)
        return f"{name} ({self.mount_point}) — {size_gb:.1f} GB"


class UsbManager:
    """Detects and monitors physical removable USB storage devices."""

    @classmethod
    def list_removable_drives(cls) -> List[UsbDevice]:
        """
        Enumerates connected removable storage drives across Linux, macOS, and Windows.
        Returns a list of UsbDevice objects.
        """
        system = platform.system()
        if system == "Linux":
            return cls._list_linux()
        elif system == "Darwin":
            return cls._list_macos()
        elif system == "Windows":
            return cls._list_windows()
        else:
            return cls._list_fallback()

    @classmethod
    def _list_linux(cls) -> List[UsbDevice]:
        drives: List[UsbDevice] = []

        # Try lsblk JSON first for rich device metadata
        try:
            res = subprocess.run(
                ["lsblk", "-J", "-o", "NAME,MOUNTPOINT,LABEL,FSTYPE,SIZE,RM,HOTPLUG,UUID,ROTA"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if res.returncode == 0:
                import json
                data = json.loads(res.stdout)
                devices = data.get("blockdevices", [])

                def walk(devs):
                    for dev in devs:
                        mount = dev.get("mountpoint")
                        # RM (removable) or hotplug or mounted under /media or /run/media or /mnt
                        is_rm = dev.get("rm") in (True, 1, "1") or dev.get("hotplug") in (True, 1, "1")
                        if mount:
                            if is_rm or "/media" in mount or "/run/media" in mount or "/mnt" in mount:
                                total, free = cls._get_disk_usage(mount)
                                drives.append(UsbDevice(
                                    device_id=dev.get("name", "unknown"),
                                    mount_point=mount,
                                    label=dev.get("label") or os.path.basename(mount) or "USB Drive",
                                    filesystem=dev.get("fstype", "unknown"),
                                    total_bytes=total,
                                    free_bytes=free,
                                    is_removable=True,
                                    uuid=dev.get("uuid")
                                ))
                        if "children" in dev:
                            walk(dev["children"])

                walk(devices)
                if drives:
                    return drives
        except Exception:
            pass

        # Fallback inspection of /media, /run/media, and /mnt
        return cls._list_fallback()

    @classmethod
    def _list_macos(cls) -> List[UsbDevice]:
        drives: List[UsbDevice] = []
        volumes_path = "/Volumes"
        if os.path.exists(volumes_path):
            try:
                for entry in os.listdir(volumes_path):
                    vol_dir = os.path.join(volumes_path, entry)
                    # Skip Macintosh HD root symlink
                    if os.path.islink(vol_dir) and os.path.realpath(vol_dir) == "/":
                        continue
                    if os.path.isdir(vol_dir):
                        total, free = cls._get_disk_usage(vol_dir)
                        drives.append(UsbDevice(
                            device_id=entry,
                            mount_point=vol_dir,
                            label=entry,
                            filesystem="apfs/exfat",
                            total_bytes=total,
                            free_bytes=free,
                            is_removable=True,
                            uuid=None
                        ))
            except Exception:
                pass
        return drives

    @classmethod
    def _list_windows(cls) -> List[UsbDevice]:
        drives: List[UsbDevice] = []
        try:
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter_idx in range(26):
                if bitmask & (1 << letter_idx):
                    drive_letter = f"{chr(65 + letter_idx)}:\\"
                    # DRIVE_REMOVABLE = 2
                    drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_letter)
                    if drive_type == 2 or drive_letter.upper() not in ("C:\\", "D:\\"):
                        total, free = cls._get_disk_usage(drive_letter)
                        drives.append(UsbDevice(
                            device_id=drive_letter,
                            mount_point=drive_letter,
                            label=f"Removable Drive ({drive_letter[:2]})",
                            filesystem="FAT32/NTFS",
                            total_bytes=total,
                            free_bytes=free,
                            is_removable=(drive_type == 2),
                            uuid=None
                        ))
        except Exception:
            pass
        return drives

    @classmethod
    def _list_fallback(cls) -> List[UsbDevice]:
        drives: List[UsbDevice] = []
        candidate_dirs = [
            "/media",
            f"/run/media/{os.environ.get('USER', '')}",
            "/mnt"
        ]
        for base in candidate_dirs:
            if os.path.exists(base) and os.path.isdir(base):
                try:
                    for item in os.listdir(base):
                        full = os.path.join(base, item)
                        if os.path.isdir(full):
                            total, free = cls._get_disk_usage(full)
                            drives.append(UsbDevice(
                                device_id=item,
                                mount_point=full,
                                label=item,
                                filesystem="generic",
                                total_bytes=total,
                                free_bytes=free,
                                is_removable=True,
                                uuid=None
                            ))
                except Exception:
                    pass
        return drives

    @staticmethod
    def _get_disk_usage(path: str) -> tuple[int, int]:
        try:
            usage = shutil.disk_usage(path)
            return usage.total, usage.free
        except Exception:
            return 0, 0

    @classmethod
    def is_drive_connected(cls, mount_point: str) -> bool:
        """Returns True if mount_point exists and is readable."""
        if not mount_point:
            return False
        return os.path.exists(mount_point) and os.path.isdir(mount_point)
