"""Base model abstraction for unified image processing."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import time


class TaskType(Enum):
    """Supported image processing task types."""
    REMOVE_BG = "remove-bg"
    GENERATE = "generate"
    EDIT = "edit"
    ANALYZE = "analyze"
    ENHANCE = "enhance"


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
            return f"Error: {self.error}"

        cost_str = 'Free' if self.cost == 0 else f'${self.cost:.4f}'
        return f"""Processed with {self.model_used}
  Confidence: {self.confidence:.1%}
  Time: {self.processing_time:.1f}s
  Cost: {cost_str}
  Output: {self.output_path}"""


@dataclass
class TaskConfig:
    """Unified configuration for all image processing tasks."""
    task_type: TaskType
    quality_mode: str = 'high'  # 'low', 'medium', 'high', 'premium', 'auto'
    output_path: Optional[str] = None
    output_format: str = 'png'
    prefer_free: bool = True
    model_preference: str = 'auto'  # 'auto', 'nano-banana', 'gemini25', 'removebg'

    # Generation/editing specific
    prompt: Optional[str] = None
    instruction: Optional[str] = None
    reference_images: List[str] = field(default_factory=list)

    @classmethod
    def for_remove_bg(cls, output_path: str = None, quality: str = 'high') -> 'TaskConfig':
        """Create config for background removal."""
        return cls(
            task_type=TaskType.REMOVE_BG,
            quality_mode=quality,
            output_path=output_path
        )

    @classmethod
    def for_generate(cls, prompt: str, output_path: str = None,
                     quality: str = 'auto', references: List[str] = None) -> 'TaskConfig':
        """Create config for image generation."""
        return cls(
            task_type=TaskType.GENERATE,
            quality_mode=quality,
            output_path=output_path,
            prompt=prompt,
            reference_images=references or []
        )

    @classmethod
    def for_edit(cls, instruction: str, output_path: str = None,
                 quality: str = 'auto', references: List[str] = None) -> 'TaskConfig':
        """Create config for image editing."""
        return cls(
            task_type=TaskType.EDIT,
            quality_mode=quality,
            output_path=output_path,
            instruction=instruction,
            reference_images=references or []
        )


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
        Process an existing image (bg removal, editing, analysis).

        Args:
            image_path: Path to input image
            task_config: Task configuration

        Returns:
            ProcessingResult with output and metrics
        """
        pass

    def generate_image(self, task_config: TaskConfig) -> ProcessingResult:
        """
        Generate new image from prompt. Override if supported.

        Args:
            task_config: Task configuration with prompt

        Returns:
            ProcessingResult with generated image
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support generation")

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return model capabilities and characteristics.

        Returns:
            Dict with:
                - tasks: List of supported TaskType values
                - cost: 'free' or 'paid'
                - avg_time: Average processing time in seconds
                - quality_score: Quality score 0-1
                - cost_per_image: Cost per image (if paid)
        """
        pass

    def supports_task(self, task_type: TaskType) -> bool:
        """Check if model supports a task type."""
        return task_type in self.get_capabilities()['tasks']

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
