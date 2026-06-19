import os
import pytest
from unittest.mock import MagicMock
import env
from models import TaskConfig, TaskType, ProcessingResult, BaseModel
from router import ModelRouter, create_default_router

class MockModel(BaseModel):
    def __init__(self, name, tasks, quality=0.9, cost='free', health=True):
        super().__init__(api_key="mock")
        self.name = name
        self._tasks = tasks
        self._quality = quality
        self._cost = cost
        self._health = health

    def get_capabilities(self):
        return {
            'tasks': self._tasks,
            'cost': self._cost,
            'avg_time': 1.0,
            'quality_score': self._quality,
            'cost_per_image': 0.01 if self._cost == 'paid' else 0.0
        }
    
    def process_image(self, path, config):
        return ProcessingResult(
            model_used=self.name,
            confidence=1.0,
            processing_time=0.1,
            cost=0.0,
            output_path="out.png",
            metadata={},
            success=True
        )
    
    def health_check(self):
        return self._health

def test_router_selects_best_quality():
    # Setup models
    fast_model = MockModel("Fast", [TaskType.REMOVE_BG], quality=0.8, cost='free')
    pro_model = MockModel("Pro", [TaskType.REMOVE_BG], quality=0.99, cost='free')
    
    router = ModelRouter([fast_model, pro_model])
    
    # Request high quality
    config = TaskConfig(TaskType.REMOVE_BG, quality_mode='premium')
    selected = router.select_model(config)
    
    assert selected.name == "Pro"

def test_router_avoids_paid_if_free_preferred():
    # Setup models
    paid_model = MockModel("Paid", [TaskType.REMOVE_BG], quality=0.99, cost='paid')
    free_model = MockModel("Free", [TaskType.REMOVE_BG], quality=0.95, cost='free')
    
    router = ModelRouter([paid_model, free_model], prefer_free=True)
    
    # Even though paid is slightly better quality, free should be preferred by config default
    config = TaskConfig(TaskType.REMOVE_BG, quality_mode='high', prefer_free=True)
    selected = router.select_model(config)
    
    assert selected.name == "Free"

def test_router_fallback_to_paid_if_needed():
    # Setup models - Free one is broken/unhealthy
    paid_model = MockModel("Paid", [TaskType.REMOVE_BG], quality=0.99, cost='paid')
    free_model = MockModel("Free", [TaskType.REMOVE_BG], quality=0.95, cost='free', health=False)
    
    router = ModelRouter([paid_model, free_model], prefer_free=True)
    
    config = TaskConfig(TaskType.REMOVE_BG)
    selected = router.select_model(config)
    
    # Should skip the unhealthy free model and pick the paid one
    assert selected.name == "Paid"

def test_router_returns_none_when_all_unhealthy():
    # Both models unhealthy — no fallback possible
    paid_model = MockModel("Paid", [TaskType.REMOVE_BG], quality=0.99, cost='paid', health=False)
    free_model = MockModel("Free", [TaskType.REMOVE_BG], quality=0.95, cost='free', health=False)

    router = ModelRouter([paid_model, free_model], prefer_free=True)

    config = TaskConfig(TaskType.REMOVE_BG)
    selected = router.select_model(config)

    assert selected is None

def test_generation_model_selection():
    # Generation request should route to generation-capable model
    gen_model = MockModel("Gen", [TaskType.GENERATE], quality=0.9)
    edit_model = MockModel("Edit", [TaskType.REMOVE_BG], quality=0.9)
    
    router = ModelRouter([gen_model, edit_model])
    
    config = TaskConfig.for_generate("A cat")
    selected = router.select_model(config)

    assert selected.name == "Gen"


_KEY_VARS = ("GEMINI_API_KEY", "NANO_BANANA_API_KEY", "GOOGLE_API_KEY",
             "REMOVE_BG_API_KEY", "REMOVEBG_API_KEY")


def test_create_default_router_bootstraps_keys_in_bare_shell(monkeypatch):
    """Regression for the RG-0030 'All models failed' incident.

    The CLI scripts (clean.py etc.) put image-processor/lib on sys.path and
    import `router`/`models` as TOP-LEVEL modules, so lib/__init__.py — where
    v1.6 placed the bootstrap_keys() call — never runs. Over the bare
    mac-bridge shell (~/.zshrc never sourced) the key is therefore never
    resolved, every model's health_check() is False, the fallback chain is
    empty, and the router returns "All models failed" without one HTTP call.

    create_default_router() must resolve keys itself so the CLI path works.
    """
    # Simulate the bare bridge shell: no API keys exported.
    for var in _KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    # Make the Keychain step deterministic (no dependency on the real `security`).
    fake = "AIza" + "x" * 35
    monkeypatch.setattr(
        env, "_from_keychain",
        lambda name: fake if name in ("GEMINI_API_KEY", "NANO_BANANA_API_KEY") else None,
    )

    router = create_default_router()
    gemini = next(m for m in router.models
                  if m.__class__.__name__ == "GeminiImageModel")

    # Before the fix this is False (api_key=None → health_check False).
    assert gemini.health_check() is True
    assert os.environ.get("GEMINI_API_KEY") == fake


def test_empty_fallback_chain_reports_missing_key():
    """An empty fallback chain (no healthy model) must say WHY, not just
    'All models failed' — the vague message is what got the 429 misdiagnosis.
    """
    dead = MockModel("Dead", [TaskType.EDIT], quality=0.96, cost='free', health=False)
    router = ModelRouter([dead])

    result = router.process_with_fallback(
        "x.jpg", TaskConfig.for_edit(instruction="noop"))

    assert result.success is False
    msg = (result.error or "").lower()
    assert "no healthy model" in msg
    assert "gemini_api_key" in msg
