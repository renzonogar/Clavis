"""
Test runner script for Clavis test suite.
Can be invoked directly via `python3 run_tests.py` or through `pytest`.
"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, "src")
TESTS_DIR = os.path.join(BASE_DIR, "tests")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def run_tests():
    # If pytest is installed, prefer pytest
    try:
        import pytest
        print(f"[*] Running test suite with pytest from: {TESTS_DIR}")
        exit_code = pytest.main(["-v", TESTS_DIR])
        return exit_code
    except ImportError:
        print("[*] pytest not found, executing tests using built-in test runner...")

    # Discover and run using unittest
    import importlib.util

    test_files = [
        "test_crypto.py",
        "test_vault.py",
        "test_storage.py",
        "test_password_generator.py",
        "test_session.py"
    ]

    total_passed = 0
    total_failed = 0

    class TempPath:
        def __init__(self):
            import tempfile
            from pathlib import Path
            self._td = tempfile.mkdtemp(prefix="clavis_test_")
            self.path = Path(self._td)
        def __truediv__(self, other):
            return self.path / other
        def __str__(self):
            return str(self.path)
        def clean(self):
            import shutil
            shutil.rmtree(self._td, ignore_errors=True)

    class PytestRaises:
        def __init__(self, exc):
            self.exc = exc
            self.value = None
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                raise AssertionError(f"Expected exception {self.exc} was not raised.")
            if not issubclass(exc_type, self.exc):
                return False
            self.value = exc_val
            return True

    # Inject mock pytest helper into sys.modules if pytest isn't available
    if "pytest" not in sys.modules:
        import types
        fake_pytest = types.ModuleType("pytest")
        fake_pytest.raises = PytestRaises
        sys.modules["pytest"] = fake_pytest

    for tf in test_files:
        path = os.path.join(TESTS_DIR, tf)
        spec = importlib.util.spec_from_file_location(tf[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Find test functions
        for attr in dir(mod):
            if attr.startswith("test_") and callable(getattr(mod, attr)):
                fn = getattr(mod, attr)
                # Check if expects tmp_path argument
                import inspect
                sig = inspect.signature(fn)
                tp = None
                try:
                    if "tmp_path" in sig.parameters:
                        tp = TempPath()
                        fn(tp)
                    else:
                        fn()
                    print(f"  [PASS] {tf}::{attr}")
                    total_passed += 1
                except Exception as e:
                    print(f"  [FAIL] {tf}::{attr} -> {e}")
                    import traceback
                    traceback.print_exc()
                    total_failed += 1
                finally:
                    if tp:
                        tp.clean()

    print(f"\nResults: {total_passed} passed, {total_failed} failed.")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
