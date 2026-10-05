"""
Tests for Clavis Session Security and Inactivity Timeout:
- Idle timeout countdown
- User activity reset
- Automatic lock execution and callback dispatch
- USB presence monitoring and disconnection response
"""

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from clavis.vault import ClavisVault
from clavis.session import SessionManager
from clavis.kdf import Argon2idParams

FAST_PARAMS = Argon2idParams(time_cost=1, memory_cost=4096, parallelism=1)


def test_session_inactivity_timeout(tmp_path):
    vault_file = str(tmp_path / "session_test.vault")
    vault = ClavisVault.create_new(vault_file, "SessionMasterKey#123", kdf_params=FAST_PARAMS)
    assert vault.is_unlocked is True

    # Set 2-second timeout
    session = SessionManager(vault, timeout_seconds=2)
    assert session.get_remaining_seconds() <= 2

    locked_events = []
    session.on_locked(lambda: locked_events.append("locked"))

    # Immediately check inactivity -> should not lock
    assert session.check_inactivity() is False
    assert vault.is_unlocked is True

    # Simulate activity reset
    time.sleep(0.5)
    session.record_activity()
    assert session.get_remaining_seconds() >= 1

    # Simulate passage of time past timeout
    session.last_activity_time = time.time() - 3
    assert session.check_inactivity() is True
    assert vault.is_unlocked is False
    assert "locked" in locked_events


def test_session_usb_disconnection(tmp_path):
    temp_dir = tmp_path / "removable_usb"
    os.makedirs(temp_dir)
    vault_file = str(temp_dir / "usb.vault")

    vault = ClavisVault.create_new(vault_file, "UsbMasterKey#123", kdf_params=FAST_PARAMS)
    session = SessionManager(vault)

    disconnect_events = []
    session.on_usb_disconnected(lambda: disconnect_events.append("disconnected"))

    # While directory exists
    assert session.check_usb_presence() is True
    assert vault.is_unlocked is True

    # Simulate USB drive unplugged / directory removed
    import shutil
    shutil.rmtree(temp_dir)
    assert session.check_usb_presence() is False
    assert vault.is_unlocked is False
    assert "disconnected" in disconnect_events
