"""Gemini Image model for generation and editing."""
import os
import base64
import time
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    from .base import BaseModel, ProcessingResult, TaskConfig, TaskType
except ImportError:
    from base import BaseModel, ProcessingResult, TaskConfig, TaskType


class GeminiAPIError(Exception):
    """Base exception for Gemini API errors."""
    pass


class GeminiImageModel(BaseModel):
    """
    Unified Gemini model for image generation and editing.

    Supports:
    - Text-to-image generation
    - Image-to-image editing with natural language
    - Multi-image composition with references
    - Auto model selection (fast vs pro)
    """

    # Model identifiers
    # gemini-3.1-flash-image-preview: 4K output, Flash tier (faster/cheaper than 3-pro), preview status.
    # gemini-3-pro-image-preview: 4K output, "thinking mode" for complex edits, preview status.
    # gemini-2.5-flash-image: 1K output cap (deprecated for this skill — too lossy on product photos).
    MODEL_FLASH = "gemini-3.1-flash-image-preview"
    MODEL_PRO = "gemini-3-pro-image-preview"

    # API configuration
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    TIMEOUT = 60

    # Supported formats
    MIME_TYPES = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }

    def __init__(self, api_key: str = None, default_model: str = None):
        super().__init__(api_key or os.getenv('GEMINI_API_KEY'))
        # Resolution order: explicit arg > GEMINI_IMAGE_MODEL env > MODEL_FLASH default.
        # The env-var hook lets clean.py's --pro flag swap to MODEL_PRO without
        # threading a constructor argument through the router.
        self.default_model = (
            default_model
            or os.getenv('GEMINI_IMAGE_MODEL')
            or self.MODEL_FLASH
        )

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Gemini image generation/editing capabilities."""
        return {
            'tasks': [TaskType.GENERATE, TaskType.EDIT],
            'cost': 'free',
            'avg_time': 12.0,
            'quality_score': 0.96,
            'cost_per_image': 0.0
        }

    def process_image(self, image_path: str, task_config: TaskConfig) -> ProcessingResult:
        """Edit existing image with instruction."""
        if task_config.task_type != TaskType.EDIT:
            raise ValueError(f"Use generate_image() for {task_config.task_type}")

        start_time = time.time()

        try:
            model = self._select_model(
                task_config.instruction or "",
                task_config.reference_images,
                task_config.quality_mode
            )

            image_data, metadata = self._edit_image(
                input_image=image_path,
                instruction=task_config.instruction,
                model=model,
                reference_images=task_config.reference_images
            )

            output_path = task_config.output_path or self._default_output_path(
                image_path, "-edited", task_config.output_format
            )

            self._save_image(image_data, output_path)

            processing_time = time.time() - start_time
            self._record_call(processing_time, 0.0, True)

            return ProcessingResult(
                model_used=f"Gemini ({model})",
                confidence=0.95,
                processing_time=processing_time,
                cost=0.0,
                output_path=output_path,
                metadata=metadata,
                success=True
            )

        except Exception as e:
            processing_time = time.time() - start_time
            self._record_call(processing_time, 0.0, False)
            return ProcessingResult(
                model_used='Gemini',
                confidence=0.0,
                processing_time=processing_time,
                cost=0.0,
                output_path='',
                metadata={'error': str(e)},
                success=False,
                error=str(e)
            )

    def generate_image(self, task_config: TaskConfig) -> ProcessingResult:
        """Generate new image from prompt."""
        if not task_config.prompt:
            raise ValueError("prompt is required for generation")

        start_time = time.time()

        try:
            model = self._select_model(
                task_config.prompt,
                task_config.reference_images,
                task_config.quality_mode
            )

            image_data, metadata = self._generate_image(
                prompt=task_config.prompt,
                model=model,
                reference_images=task_config.reference_images
            )

            output_path = task_config.output_path or f"generated-{int(time.time())}.png"

            self._save_image(image_data, output_path)

            processing_time = time.time() - start_time
            self._record_call(processing_time, 0.0, True)

            return ProcessingResult(
                model_used=f"Gemini ({model})",
                confidence=0.95,
                processing_time=processing_time,
                cost=0.0,
                output_path=output_path,
                metadata=metadata,
                success=True
            )

        except Exception as e:
            processing_time = time.time() - start_time
            self._record_call(processing_time, 0.0, False)
            return ProcessingResult(
                model_used='Gemini',
                confidence=0.0,
                processing_time=processing_time,
                cost=0.0,
                output_path='',
                metadata={'error': str(e)},
                success=False,
                error=str(e)
            )

    def _select_model(self, prompt: str, reference_images: List[str] = None,
                      quality_hint: str = "auto") -> str:
        """Select appropriate model based on task complexity.

        Resolution order:
          1. GEMINI_IMAGE_MODEL env var (explicit override, never auto-escalates)
          2. quality_hint == "fast"     -> MODEL_FLASH
          3. quality_hint in ("pro","premium") -> MODEL_PRO
          4. Auto-heuristics on the prompt content (kept narrow — only
             upgrades when the caller's prompt or refs clearly need pro tier).
        """
        env_override = os.getenv('GEMINI_IMAGE_MODEL')
        if env_override:
            return env_override

        if quality_hint == "fast":
            return self.MODEL_FLASH
        elif quality_hint in ("pro", "premium"):
            return self.MODEL_PRO

        # Auto-selection heuristics. NOTE: these scan caller-supplied prompt
        # text for trigger words. Be conservative — every match here is a 4×
        # cost upgrade (Pro vs Flash). The previous "professional" /
        # "detailed" matches were too eager and silently escalated catalog-
        # cleanup prompts. Set GEMINI_IMAGE_MODEL to pin the choice.
        num_refs = len(reference_images) if reference_images else 0
        use_pro = (
            num_refs >= 8 or
            "render at 4k" in prompt.lower() or
            "use the pro model" in prompt.lower()
        )

        return self.MODEL_PRO if use_pro else self.MODEL_FLASH

    def _generate_image(self, prompt: str, model: str,
                        reference_images: List[str] = None) -> tuple:
        """Generate image from text prompt."""
        parts = [{"text": prompt}]

        if reference_images:
            for img_path in reference_images:
                image_data = self._encode_image(img_path)
                mime_type = self._get_mime_type(img_path)
                parts.insert(0, {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_data
                    }
                })

        url = f"{self.BASE_URL}/models/{model}:generateContent?key={self.api_key}"
        payload = {"contents": [{"parts": parts}]}

        response = requests.post(url, json=payload, timeout=self.TIMEOUT)
        response.raise_for_status()

        data = response.json()
        image_bytes = self._extract_image_from_response(data)

        if not image_bytes:
            raise GeminiAPIError("No image data in response")

        metadata = {
            "model": model,
            "prompt": prompt,
            "reference_count": len(reference_images) if reference_images else 0
        }

        return image_bytes, metadata

    def _edit_image(self, input_image: str, instruction: str, model: str,
                    reference_images: List[str] = None) -> tuple:
        """Edit existing image with instruction."""
        parts = []

        # Input image first
        image_data = self._encode_image(input_image)
        mime_type = self._get_mime_type(input_image)
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": image_data
            }
        })

        # Reference images
        if reference_images:
            for ref_path in reference_images:
                ref_data = self._encode_image(ref_path)
                ref_mime = self._get_mime_type(ref_path)
                parts.append({
                    "inline_data": {
                        "mime_type": ref_mime,
                        "data": ref_data
                    }
                })

        # Instruction text
        parts.append({"text": instruction})

        url = f"{self.BASE_URL}/models/{model}:generateContent?key={self.api_key}"
        payload = {"contents": [{"parts": parts}]}

        response = requests.post(url, json=payload, timeout=self.TIMEOUT)
        response.raise_for_status()

        data = response.json()
        image_bytes = self._extract_image_from_response(data)

        if not image_bytes:
            raise GeminiAPIError("No image data in response")

        metadata = {
            "model": model,
            "instruction": instruction,
            "input_image": Path(input_image).name,
            "reference_count": len(reference_images) if reference_images else 0
        }

        return image_bytes, metadata

    def _extract_image_from_response(self, data: dict) -> Optional[bytes]:
        """Extract image bytes from API response."""
        # Try multiple response structures
        for candidate in data.get('candidates', []):
            # Structure 1: candidates[].content.parts[].inlineData
            for part in candidate.get('content', {}).get('parts', []):
                if 'inlineData' in part:
                    return base64.b64decode(part['inlineData']['data'])
                elif 'inline_data' in part:
                    return base64.b64decode(part['inline_data']['data'])

            # Structure 2: candidates[].parts[].inlineData
            for part in candidate.get('parts', []):
                if 'inlineData' in part:
                    return base64.b64decode(part['inlineData']['data'])
                elif 'inline_data' in part:
                    return base64.b64decode(part['inline_data']['data'])

        return None

    @staticmethod
    def _encode_image(image_path: str) -> str:
        """Encode image to base64."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')

    @staticmethod
    def _get_mime_type(image_path: str) -> str:
        """Get MIME type from file extension."""
        ext = Path(image_path).suffix.lower()
        return GeminiImageModel.MIME_TYPES.get(ext, 'image/jpeg')

    @staticmethod
    def _save_image(image_data: bytes, output_path: str):
        """Save image bytes to file."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(image_data)

    @staticmethod
    def _default_output_path(input_path: str, suffix: str, fmt: str) -> str:
        """Generate default output path."""
        p = Path(input_path)
        return str(p.parent / f"{p.stem}{suffix}.{fmt}")
