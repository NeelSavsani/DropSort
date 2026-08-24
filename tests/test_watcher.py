"""Unit tests for Watcher module."""

from pathlib import Path
import tempfile
import time
import pytest

from dropsort.watcher import is_file_ready_and_stable


def test_is_file_ready_and_stable():
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "sample.txt"
        assert is_file_ready_and_stable(f, check_interval=0.05, retries=2) is False

        f.write_text("stable content ready")
        assert is_file_ready_and_stable(f, check_interval=0.05, retries=2) is True
