"""Base model abstraction for image processing."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import time


@dataclass
class ProcessingResult:
    """Result from image processing."""
    model_used: str
    confidence: float
    processing_time: float
    cost: float
    output_path: str
    metadata: Dict[str, Any]
    success: bool
    error: Optional[str] = None
    
    def __str__(self):
        if not self.success:
            return f"❌ Error: {self.error}"
        
        cost_str = 'Free' if self.cost == 0 else f'${self.cost:.4f}'
        return f"""✓ Processed with {self.model_used}
  Confidence: {self.confidence:.1%}
  Time: {self.processing_time:.1f}s
  Cost: {cost_str}
  Output: {self.output_path}"""


@dataclass
class TaskConfig:
    """Configuration for an image processing task."""
    task_type: str  # 'remove-bg', 'enhance', 'analyze'
    quality_mode: str = 'high'  # 'low', 'medium', 'high', 'premium'
    output_path: Optional[str] = None
    output_format: str = 'png'
    prefer_free: bool = True


class BaseModel(ABC):
    """Abstract base class for all image processing models."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.stats = {
            'calls': 0,
            'errors': 0,
            'total_time': 0.0,
            'total_cost': 0.0
        }
    
    @abstractmethod
    def process_image(self, image_path: str, task_config: TaskConfig) -> ProcessingResult:
        """
        Process an image according to the task configuration.
        
        Args:
            image_path: Path to input image
            task_config: Task configuration
            
        Returns:
            ProcessingResult with output and metrics
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return model capabilities and characteristics.
        
        Returns:
            Dict with:
                - tasks: List of supported task types
                - cost: 'free' or 'paid'
                - avg_time: Average processing time in seconds
                - quality_score: Quality score 0-1
                - cost_per_image: Cost per image (if paid)
        """
        pass
    
    def health_check(self) -> bool:
        """Check if model is available and healthy."""
        return self.api_key is not None
    
    def _record_call(self, processing_time: float, cost: float, success: bool):
        """Record call statistics."""
        self.stats['calls'] += 1
        self.stats['total_time'] += processing_time
        self.stats['total_cost'] += cost
        if not success:
            self.stats['errors'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get model statistics."""
        return {
            **self.stats,
            'success_rate': (self.stats['calls'] - self.stats['errors']) / max(self.stats['calls'], 1),
            'avg_time': self.stats['total_time'] / max(self.stats['calls'], 1)
        }
