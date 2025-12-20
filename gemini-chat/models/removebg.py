"""remove.bg API model implementation."""
import os
import time
import requests
from pathlib import Path
from typing import Dict, Any

from .base import BaseModel, ProcessingResult, TaskConfig


class RemoveBgModel(BaseModel):
    """remove.bg API image processing model."""
    
    def __init__(self, api_key: str = None):
        super().__init__(api_key or os.getenv('REMOVE_BG_API_KEY'))
        self.base_url = 'https://api.remove.bg/v1.0'
        self.cost_per_image = 0.009
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return remove.bg capabilities."""
        return {
            'tasks': ['remove-bg'],
            'cost': 'paid',
            'avg_time': 2.8,
            'quality_score': 1.0,  # Premium quality
            'cost_per_image': self.cost_per_image
        }
    
    def process_image(self, image_path: str, task_config: TaskConfig) -> ProcessingResult:
        """Process image with remove.bg."""
        start_time = time.time()
        
        try:
            if task_config.task_type == 'remove-bg':
                return self._remove_background(image_path, task_config, start_time)
            else:
                raise ValueError(f"Unsupported task: {task_config.task_type}")
                
        except Exception as e:
            processing_time = time.time() - start_time
            self._record_call(processing_time, 0.0, False)
            return ProcessingResult(
                model_used='remove.bg',
                confidence=1.0,  # remove.bg doesn't provide confidence
                processing_time=processing_time,
                cost=0.0,
                output_path='',
                metadata={'error': str(e)},
                success=False,
                error=str(e)
            )
    
    def _remove_background(self, image_path: str, task_config: TaskConfig, start_time: float) -> ProcessingResult:
        """Remove background using remove.bg API."""
        # Generate output path
        if task_config.output_path:
            output_path = task_config.output_path
        else:
            input_path = Path(image_path)
            output_path = str(input_path.parent / f"{input_path.stem}-nobg.{task_config.output_format}")
        
        # Call remove.bg API
        with open(image_path, 'rb') as image_file:
            response = requests.post(
                f"{self.base_url}/removebg",
                files={'image_file': image_file},
                headers={'X-Api-Key': self.api_key},
                timeout=30
            )
        
        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text}")
        
        # Save result
        with open(output_path, 'wb') as out_file:
            out_file.write(response.content)
        
        processing_time = time.time() - start_time
        self._record_call(processing_time, self.cost_per_image, True)
        
        return ProcessingResult(
            model_used='remove.bg',
            confidence=1.0,  # Premium quality, no confidence score
            processing_time=processing_time,
            cost=self.cost_per_image,
            output_path=output_path,
            metadata={
                'credits_charged': response.headers.get('X-Credits-Charged', 1)
            },
            success=True
        )
