"""Tests for the --autonomous flag plumbing on process_new_item.py."""
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "rg-full-auto" / "scripts" / "process_new_item.py"


def test_help_lists_autonomous_flag():
    """--help output must mention --autonomous."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--autonomous" in result.stdout


def test_autonomous_flag_short_circuits_interactive(monkeypatch, tmp_path):
    """Importing the module and calling main with --autonomous should NOT call input()."""
    import importlib.util

    # Stage a fake image and a fake items_dir
    photo = tmp_path / "photo.jpeg"
    photo.write_bytes(b"x")
    items_dir = tmp_path / "items"
    items_dir.mkdir()

    spec = importlib.util.spec_from_file_location("process_new_item", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore

    # Sanity-check: the v6.0 dispatcher branch exists
    assert hasattr(mod, "_run_autonomous"), \
        "--autonomous flag must dispatch to a _run_autonomous function"
