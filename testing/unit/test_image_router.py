import pytest
from unittest.mock import MagicMock
from models import TaskConfig, TaskType, ProcessingResult, BaseModel
from router import ModelRouter

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

def test_generation_model_selection():
    # Generation request should route to generation-capable model
    gen_model = MockModel("Gen", [TaskType.GENERATE], quality=0.9)
    edit_model = MockModel("Edit", [TaskType.REMOVE_BG], quality=0.9)
    
    router = ModelRouter([gen_model, edit_model])
    
    config = TaskConfig.for_generate("A cat")
    selected = router.select_model(config)
    
    assert selected.name == "Gen"
