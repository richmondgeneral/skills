"""remove.bg API model implementation."""
import os
import time
import requests
from pathlib import Path
from typing import Dict, Any, Tuple

try:
    from .base import BaseModel, ProcessingResult, TaskConfig, TaskType
except ImportError:
    from base import BaseModel, ProcessingResult, TaskConfig, TaskType


class RemoveBgModel(BaseModel):
    """remove.bg API image processing model."""

    def __init__(self, api_key: str = None):
        super().__init__(api_key or os.getenv('REMOVE_BG_API_KEY'))
        self.base_url = 'https://api.remove.bg/v1.0'
        self.cost_per_image = 0.009

    def get_capabilities(self) -> Dict[str, Any]:
        """Return remove.bg capabilities."""
        return {
            'tasks': [TaskType.REMOVE_BG],
            'cost': 'paid',
            'avg_time': 2.8,
            'quality_score': 1.0,  # Premium quality
            'cost_per_image': self.cost_per_image
        }

    def process_image(self, image_path: str, task_config: TaskConfig) -> ProcessingResult:
        """Process image with remove.bg."""
        start_time = time.time()

        try:
            if task_config.task_type == TaskType.REMOVE_BG:
                return self._remove_background(image_path, task_config, start_time)
            else:
                raise ValueError(f"Unsupported task: {task_config.task_type}")

        except Exception as e:
            processing_time = time.time() - start_time
            self._record_call(processing_time, 0.0, False)
            return ProcessingResult(
                model_used='remove.bg',
                confidence=1.0,
                processing_time=processing_time,
                cost=0.0,
                output_path='',
                metadata={'error': str(e)},
                success=False,
                error=str(e)
            )

    def _remove_background(self, image_path: str, task_config: TaskConfig, start_time: float) -> ProcessingResult:
        """Remove background using remove.bg API."""
        if task_config.output_path:
            output_path = task_config.output_path
        else:
            input_path = Path(image_path)
            output_path = str(input_path.parent / f"{input_path.stem}-nobg.{task_config.output_format}")

        response, payload_used = self._call_removebg_with_fallbacks(image_path)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as out_file:
            out_file.write(response.content)

        processing_time = time.time() - start_time
        self._record_call(processing_time, self.cost_per_image, True)

        return ProcessingResult(
            model_used='remove.bg',
            confidence=1.0,
            processing_time=processing_time,
            cost=self.cost_per_image,
            output_path=output_path,
            metadata={
                'credits_charged': response.headers.get('X-Credits-Charged', 1),
                'credits_remaining': response.headers.get('X-Credits-Remaining'),
                'request_profile': payload_used
            },
            success=True
        )

    def _call_removebg_with_fallbacks(self, image_path: str) -> Tuple[requests.Response, str]:
        """
        Call remove.bg with retries and profile fallbacks.

        Returns:
            Tuple of (successful HTTP response, profile label used)
        """
        profiles = [
            ('product', {'size': 'auto', 'type': 'product', 'format': 'png'}),
            ('generic_png', {'size': 'auto', 'format': 'png'}),
            ('basic', {'size': 'auto'}),
        ]
        max_attempts = 2
        last_error = None

        for profile_name, payload in profiles:
            for attempt in range(1, max_attempts + 1):
                try:
                    with open(image_path, 'rb') as image_file:
                        response = requests.post(
                            f"{self.base_url}/removebg",
                            files={'image_file': image_file},
                            data=payload,
                            headers={'X-Api-Key': self.api_key},
                            timeout=45
                        )
                except requests.RequestException as e:
                    last_error = f"{profile_name} attempt {attempt}: {e}"
                    if attempt < max_attempts:
                        time.sleep(0.75 * attempt)
                        continue
                    break

                if response.status_code == 200:
                    return response, profile_name

                # Retry transient upstream failures.
                if response.status_code in (429, 500, 502, 503, 504) and attempt < max_attempts:
                    last_error = (
                        f"{profile_name} attempt {attempt}: "
                        f"HTTP {response.status_code} - {response.text[:200]}"
                    )
                    time.sleep(0.75 * attempt)
                    continue

                # Profile might be rejected for this image/account; fall through to next profile.
                if response.status_code in (400, 422):
                    last_error = (
                        f"{profile_name} rejected: HTTP {response.status_code} - "
                        f"{response.text[:200]}"
                    )
                    break

                # Non-recoverable for this profile.
                last_error = f"{profile_name}: HTTP {response.status_code} - {response.text[:200]}"
                break

        raise Exception(last_error or "remove.bg request failed")
