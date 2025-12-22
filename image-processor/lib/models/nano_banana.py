"""Nano Banana Pro (Gemini 3) model implementation."""
import os
import json
import base64
import time
import requests
from pathlib import Path
from PIL import Image, ImageDraw
from typing import Dict, Any

try:
    from .base import BaseModel, ProcessingResult, TaskConfig, TaskType
except ImportError:
    from base import BaseModel, ProcessingResult, TaskConfig, TaskType


class NanaBananaModel(BaseModel):
    """Nano Banana Pro (Gemini 3) image processing model."""

    def __init__(self, api_key: str = None):
        super().__init__(api_key or os.getenv('NANO_BANANA_API_KEY'))
        self.endpoint = 'gemini-3-pro-image-preview'
        self.base_url = 'https://generativelanguage.googleapis.com/v1beta'

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Nano Banana Pro capabilities."""
        return {
            'tasks': [TaskType.REMOVE_BG, TaskType.ANALYZE, TaskType.ENHANCE],
            'cost': 'free',
            'avg_time': 7.9,
            'quality_score': 0.98,
            'cost_per_image': 0.0
        }

    def process_image(self, image_path: str, task_config: TaskConfig) -> ProcessingResult:
        """Process image with Nano Banana Pro."""
        start_time = time.time()

        try:
            if task_config.task_type == TaskType.REMOVE_BG:
                return self._remove_background(image_path, task_config, start_time)
            elif task_config.task_type == TaskType.ANALYZE:
                return self._analyze_image(image_path, task_config, start_time)
            else:
                raise ValueError(f"Unsupported task: {task_config.task_type}")

        except Exception as e:
            processing_time = time.time() - start_time
            self._record_call(processing_time, 0.0, False)
            return ProcessingResult(
                model_used='Nano Banana Pro',
                confidence=0.0,
                processing_time=processing_time,
                cost=0.0,
                output_path='',
                metadata={'error': str(e)},
                success=False,
                error=str(e)
            )

    def _remove_background(self, image_path: str, task_config: TaskConfig, start_time: float) -> ProcessingResult:
        """Remove background using Nano Banana Pro."""
        bounds_data = self._detect_subject(image_path)

        if not bounds_data:
            raise Exception("Failed to detect subject")

        if task_config.output_path:
            output_path = task_config.output_path
        else:
            input_path = Path(image_path)
            output_path = str(input_path.parent / f"{input_path.stem}-nobg.{task_config.output_format}")

        self._apply_mask(image_path, output_path, bounds_data['subject_bounds'])

        processing_time = time.time() - start_time
        self._record_call(processing_time, 0.0, True)

        return ProcessingResult(
            model_used='Nano Banana Pro',
            confidence=bounds_data['confidence'],
            processing_time=processing_time,
            cost=0.0,
            output_path=output_path,
            metadata={
                'subject': bounds_data['subject_description'],
                'bounds': bounds_data['subject_bounds']
            },
            success=True
        )

    def _detect_subject(self, image_path: str) -> Dict[str, Any]:
        """Detect subject bounds using Gemini 3."""
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        url = f"{self.base_url}/models/{self.endpoint}:generateContent?key={self.api_key}"

        prompt = """Analyze this image and detect the main subject for background removal.

Return JSON with:
1. subject_bounds: {x, y, width, height} - tight bounding box around the main subject
2. confidence: 0-1 score
3. subject_description: brief description

Make the bounding box as tight as possible around the subject."""

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_data}}
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        response = requests.post(url, json=payload, timeout=30)

        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text}")

        result = response.json()
        if 'candidates' in result and len(result['candidates']) > 0:
            text = result['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text)

        raise Exception("No response from API")

    def _apply_mask(self, image_path: str, output_path: str, bounds: Dict[str, int]):
        """Apply mask to remove background."""
        img = Image.open(image_path)
        width, height = img.size

        mask = Image.new('L', (width, height), 0)
        draw = ImageDraw.Draw(mask)

        x = bounds['x']
        y = bounds['y']
        w = bounds['width']
        h = bounds['height']
        draw.rectangle([x, y, x + w, y + h], fill=255)

        img = img.convert('RGBA')
        img.putalpha(mask)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, 'PNG')

    def _analyze_image(self, image_path: str, task_config: TaskConfig, start_time: float) -> ProcessingResult:
        """Analyze image content."""
        raise NotImplementedError("Analyze task not yet implemented")
