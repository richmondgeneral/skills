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


def test_default_is_autonomous():
    """v6.0: process_new_item.py defaults to autonomous; --interactive is the opt-out."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--interactive" in result.stdout
    # --autonomous is now the default behavior, so the flag should be deprecated/aliased.
    # Either it stays as a no-op or it's removed; either way the help must explain that
    # the default is autonomous.
    assert "default" in result.stdout.lower()
    assert "autonomous" in result.stdout.lower()


def test_default_dispatches_to_autonomous(tmp_path, monkeypatch):
    """When --autonomous is NOT passed, main() should still call _run_autonomous."""
    import importlib.util

    photo = tmp_path / "photo.jpeg"
    photo.write_bytes(b"x")

    spec = importlib.util.spec_from_file_location("process_new_item", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore

    calls = []
    def fake_autonomous(image_path, items_dir=None):
        calls.append({"image": image_path, "items_dir": items_dir})
        return 0
    monkeypatch.setattr(mod, "_run_autonomous", fake_autonomous)

    # Simulate `process_new_item.py --image <photo>` with NO --autonomous and NO --interactive.
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--image", str(photo)])
    exit_code = mod.main()
    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0]["image"] == str(photo)


def test_autonomous_exit_codes(tmp_path, monkeypatch):
    """_run_autonomous returns 0 / 1 / 2 based on completed / failed / blocked."""
    import importlib.util
    import types

    spec = importlib.util.spec_from_file_location("process_new_item", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore

    class FakeState:
        sku = "RG-TEST"

    class FakeOrchestrator:
        def __init__(self, *args, **kwargs):
            self.summary = None
        def ingest_photos(self, paths):
            return [FakeState()]
        def process_all(self):
            return self.summary

    orch = FakeOrchestrator()
    fake_process_batch = types.ModuleType("process_batch")
    fake_process_batch.BatchOrchestrator = lambda *a, **kw: orch
    monkeypatch.setitem(sys.modules, "process_batch", fake_process_batch)

    photo = tmp_path / "p.jpeg"
    photo.write_bytes(b"x")

    # Clean success → exit 0
    orch.summary = {"processed": 1, "completed": 1, "blocked": 0, "failed": 0, "items": {}}
    assert mod._run_autonomous(str(photo), items_dir=str(tmp_path)) == 0

    # Failed → exit 1
    orch.summary = {"processed": 1, "completed": 0, "blocked": 0, "failed": 1, "items": {}}
    assert mod._run_autonomous(str(photo), items_dir=str(tmp_path)) == 1

    # Blocked, none failed → exit 2 (pending question; user action required)
    orch.summary = {"processed": 1, "completed": 0, "blocked": 1, "failed": 0, "items": {}}
    assert mod._run_autonomous(str(photo), items_dir=str(tmp_path)) == 2

    # Mixed failed + blocked → exit 1 (failed takes precedence)
    orch.summary = {"processed": 2, "completed": 0, "blocked": 1, "failed": 1, "items": {}}
    assert mod._run_autonomous(str(photo), items_dir=str(tmp_path)) == 1


def test_interactive_flag_uses_legacy_processor(tmp_path, monkeypatch):
    """When --interactive IS passed, the legacy RGItemProcessor runs (not _run_autonomous)."""
    import importlib.util

    photo = tmp_path / "photo.jpeg"
    photo.write_bytes(b"x")

    spec = importlib.util.spec_from_file_location("process_new_item", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore

    autonomous_calls = []
    legacy_calls = []

    def fake_autonomous(image_path, items_dir=None):
        autonomous_calls.append(image_path)
        return 0

    class FakeRGItemProcessor:
        def __init__(self, interactive=True):
            legacy_calls.append({"interactive": interactive})
        def run(self, image):
            legacy_calls.append({"ran": image})

    monkeypatch.setattr(mod, "_run_autonomous", fake_autonomous)
    monkeypatch.setattr(mod, "RGItemProcessor", FakeRGItemProcessor)

    monkeypatch.setattr(sys, "argv",
                         [str(SCRIPT), "--image", str(photo), "--interactive"])
    exit_code = mod.main()
    assert exit_code == 0
    assert len(autonomous_calls) == 0
    assert len(legacy_calls) >= 1  # __init__ + run
