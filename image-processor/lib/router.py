"""Smart model routing logic for unified image processing."""
from typing import List, Optional, Dict, Any

try:
    from .models import BaseModel, TaskConfig, ProcessingResult, TaskType
except ImportError:
    from models import BaseModel, TaskConfig, ProcessingResult, TaskType


class ModelRouter:
    """Routes image processing tasks to optimal models."""

    def __init__(self, models: List[BaseModel], prefer_free: bool = True):
        self.models = models
        self.prefer_free = prefer_free

        # Quality thresholds
        self.quality_thresholds = {
            'low': 0.85,
            'medium': 0.90,
            'high': 0.95,
            'premium': 0.98,
            'auto': 0.90  # Default for auto
        }

    def select_model(self, task_config: TaskConfig) -> Optional[BaseModel]:
        """
        Select the best model for the task.

        Args:
            task_config: Task configuration

        Returns:
            Best model or None if no suitable model found
        """
        task_type = task_config.task_type

        # Filter by capability (task support)
        capable = [m for m in self.models if m.supports_task(task_type)]

        if not capable:
            return None

        # For generation/editing, use specialized selection
        if task_type in (TaskType.GENERATE, TaskType.EDIT):
            return self._select_generation_model(capable, task_config)

        # Filter by cost if prefer_free is set
        if task_config.prefer_free:
            free_models = [m for m in capable
                          if m.get_capabilities()['cost'] == 'free']
            if free_models:
                capable = free_models

        # Filter by health check
        healthy = [m for m in capable if m.health_check()]

        if not healthy:
            return None

        # Score and select best
        return self._score_and_select(healthy, task_config)

    def _select_generation_model(self, models: List[BaseModel],
                                   task_config: TaskConfig) -> Optional[BaseModel]:
        """Apply generation-specific heuristics."""
        # Filter healthy models
        healthy = [m for m in models if m.health_check()]
        if not healthy:
            return None

        # For generation/editing, prefer GeminiImageModel
        # The model's internal _select_model handles fast vs pro
        for model in healthy:
            if model.__class__.__name__ == 'GeminiImageModel':
                return model

        # Fallback to any capable model
        return healthy[0] if healthy else None

    def _score_and_select(self, models: List[BaseModel],
                          task_config: TaskConfig) -> BaseModel:
        """Score models and select the best one."""
        quality_threshold = self.quality_thresholds.get(
            task_config.quality_mode, 0.95
        )

        scored = []
        for model in models:
            caps = model.get_capabilities()
            score = 0

            # Quality score (most important)
            quality_score = caps['quality_score']
            if quality_score >= quality_threshold:
                score += quality_score * 100  # 0-100 points
            else:
                score += quality_score * 50  # Penalty for not meeting threshold

            # Speed bonus (inverse of time)
            time_score = 10 / max(caps['avg_time'], 0.1)
            score += time_score * 20  # Weight: 20%

            # Cost penalty
            if caps['cost'] == 'paid':
                cost_penalty = caps.get('cost_per_image', 0.01) * 1000
                score -= cost_penalty

            scored.append((score, model))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def process(self, image_path: str, task_config: TaskConfig) -> ProcessingResult:
        """
        Process image with automatic model selection and fallback.

        Args:
            image_path: Path to input image (None for generation)
            task_config: Task configuration

        Returns:
            Processing result
        """
        if task_config.task_type == TaskType.GENERATE:
            return self.generate(task_config)

        return self.process_with_fallback(image_path, task_config)

    def generate(self, task_config: TaskConfig) -> ProcessingResult:
        """Generate image using best available model."""
        model = self.select_model(task_config)

        if not model:
            return ProcessingResult(
                model_used='None',
                confidence=0.0,
                processing_time=0.0,
                cost=0.0,
                output_path='',
                metadata={'error': 'No capable model found'},
                success=False,
                error='No capable model found for generation'
            )

        try:
            return model.generate_image(task_config)
        except Exception as e:
            return ProcessingResult(
                model_used=model.__class__.__name__,
                confidence=0.0,
                processing_time=0.0,
                cost=0.0,
                output_path='',
                metadata={'error': str(e)},
                success=False,
                error=str(e)
            )

    def process_with_fallback(self, image_path: str,
                               task_config: TaskConfig) -> ProcessingResult:
        """
        Process image with automatic fallback on failure.

        Args:
            image_path: Path to input image
            task_config: Task configuration

        Returns:
            Processing result from first successful model
        """
        models_to_try = self._build_fallback_chain(task_config)

        last_error = None
        for model in models_to_try:
            try:
                import sys as _sys
                print(f"Trying {model.__class__.__name__}...", file=_sys.stderr)
                result = model.process_image(image_path, task_config)

                if result.success:
                    return result

                last_error = result.error
            except Exception as e:
                last_error = str(e)
                continue

        return ProcessingResult(
            model_used='None',
            confidence=0.0,
            processing_time=0.0,
            cost=0.0,
            output_path='',
            metadata={'error': last_error or 'All models failed'},
            success=False,
            error=last_error or 'All models failed'
        )

    def _build_fallback_chain(self, task_config: TaskConfig) -> List[BaseModel]:
        """Build ordered list of models to try (fallback chain)."""
        # Default chain for remove-bg:
        # 1. Nano Banana Pro (98%, free, 7.9s)
        # 2. Gemini 2.5 Flash (95%, free, 8.4s)
        # 3. remove.bg (100%, paid, 2.8s)

        capable = [m for m in self.models if m.supports_task(task_config.task_type)]
        healthy = [m for m in capable if m.health_check()]

        def sort_key(model):
            caps = model.get_capabilities()
            cost_value = 0 if caps['cost'] == 'free' else 1
            return (-caps['quality_score'], cost_value, caps['avg_time'])

        healthy.sort(key=sort_key)
        return healthy

    def get_model_status(self) -> Dict[str, Any]:
        """Get status of all models."""
        status = {}
        for model in self.models:
            caps = model.get_capabilities()
            stats = model.get_stats()
            model_name = model.__class__.__name__

            status[model_name] = {
                'healthy': model.health_check(),
                'capabilities': {
                    **caps,
                    'tasks': [t.value for t in caps['tasks']]
                },
                'stats': stats
            }

        return status


def create_default_router(prefer_free: bool = True) -> ModelRouter:
    """Create router with all available models."""
    try:
        from .models import (
            NanaBananaModel,
            Gemini25FlashModel,
            RemoveBgModel,
            GeminiImageModel
        )
    except ImportError:
        from models import (
            NanaBananaModel,
            Gemini25FlashModel,
            RemoveBgModel,
            GeminiImageModel
        )

    models = [
        NanaBananaModel(),
        Gemini25FlashModel(),
        RemoveBgModel(),
        GeminiImageModel(),
    ]

    return ModelRouter(models, prefer_free=prefer_free)
