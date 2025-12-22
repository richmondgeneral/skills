"""Smart model routing logic."""
from typing import List, Optional, Dict, Any
from models import BaseModel, TaskConfig, ProcessingResult


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
            'premium': 0.98
        }
    
    def select_model(self, task_config: TaskConfig) -> Optional[BaseModel]:
        """
        Select the best model for the task.
        
        Args:
            task_config: Task configuration
            
        Returns:
            Best model or None if no suitable model found
        """
        # Filter by capability (task support)
        capable = [m for m in self.models 
                   if task_config.task_type in m.get_capabilities()['tasks']]
        
        if not capable:
            return None
        
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
    
    def _score_and_select(self, models: List[BaseModel], task_config: TaskConfig) -> BaseModel:
        """Score models and select the best one."""
        quality_threshold = self.quality_thresholds.get(task_config.quality_mode, 0.95)
        
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
            time_score = 10 / max(caps['avg_time'], 0.1)  # 0-100 points
            score += time_score * 20  # Weight: 20%
            
            # Cost penalty
            if caps['cost'] == 'paid':
                cost_penalty = caps.get('cost_per_image', 0.01) * 1000
                score -= cost_penalty  # Subtract cost in cents
            
            scored.append((score, model))
        
        # Sort by score (descending) and return best
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]
    
    def process_with_fallback(self, image_path: str, task_config: TaskConfig) -> ProcessingResult:
        """
        Process image with automatic fallback on failure.
        
        Args:
            image_path: Path to input image
            task_config: Task configuration
            
        Returns:
            Processing result from first successful model
        """
        # Build fallback chain based on quality
        models_to_try = self._build_fallback_chain(task_config)
        
        last_error = None
        for model in models_to_try:
            try:
                print(f"🤖 Trying {model.__class__.__name__}...")
                result = model.process_image(image_path, task_config)
                
                if result.success:
                    return result
                
                last_error = result.error
            except Exception as e:
                last_error = str(e)
                continue
        
        # All models failed
        from models import ProcessingResult
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
        
        capable = [m for m in self.models 
                   if task_config.task_type in m.get_capabilities()['tasks']]
        
        # Filter healthy models
        healthy = [m for m in capable if m.health_check()]
        
        # Sort by quality (descending), then by cost (free first)
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
                'capabilities': caps,
                'stats': stats
            }
        
        return status
