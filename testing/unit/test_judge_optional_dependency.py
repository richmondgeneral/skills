"""image-processor's agentic judge uses the google-genai SDK, but that SDK is an
OPTIONAL dependency — needed only when `clean.py --agentic` actually runs the
Best-of-3 LLM judge. Importing judge.py (and therefore clean.py, and therefore the
pure-Pillow downscale helpers/tests) must NOT require google-genai to be installed.

Regression: a module-level `from google import genai` in judge.py, combined with
clean.py importing AgentJudge at module level, coupled all of clean.py to the SDK —
breaking the downscale tests in any environment without google-genai (e.g. the
`~/.venv` the test runner uses).

These tests SIMULATE google-genai being absent (so they guard the boundary even on a
machine that happens to have the SDK installed) and assert the modules still import.
"""
import builtins
import importlib
import sys


def _block_genai(monkeypatch):
    """Force any import of google.genai to fail, as on a machine without the SDK."""
    for cached in ("clean", "models.judge"):
        sys.modules.pop(cached, None)
    real_import = builtins.__import__

    def fake_import(name, glb=None, loc=None, fromlist=(), level=0):
        if name.startswith("google.genai") or (name == "google" and fromlist and "genai" in fromlist):
            raise ImportError("simulated: google-genai not installed")
        return real_import(name, glb, loc, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_judge_module_imports_without_google_genai(monkeypatch):
    _block_genai(monkeypatch)
    mod = importlib.import_module("models.judge")
    assert hasattr(mod, "AgentJudge")


def test_clean_module_imports_without_google_genai(monkeypatch):
    # clean.py imports AgentJudge; that must not pull google.genai at module load.
    _block_genai(monkeypatch)
    mod = importlib.import_module("clean")
    assert hasattr(mod, "downscale_output_in_place")
