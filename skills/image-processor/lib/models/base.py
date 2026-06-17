"""Base model abstraction for unified image processing."""
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import time

try:
    from PIL import Image  # noqa: F401  (used by safe_save_image type hints)
except ImportError:
    Image = None  # type: ignore[assignment]

# Extension → MIME map. Conservative: covers every format Square accepts and
# every format Gemini understands for inline_data uploads. Unknown extensions
# fall back to image/jpeg (the most-tolerated value across API endpoints).
_MIME_TYPES = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    ".bmp":  "image/bmp",
    ".tif":  "image/tiff",
    ".tiff": "image/tiff",
}


def get_mime_type(path) -> str:
    """Return the image/* MIME type for `path` based on its extension.

    The providers used to hardcode "image/jpeg" for every inline_data upload,
    which (per QA) likely confused Gemini's subject-detection on PNG/WebP
    inputs and produced the crude rectangular masks that suspicious_rect_mask
    recovery exists to compensate for.
    """
    return _MIME_TYPES.get(Path(str(path)).suffix.lower(), "image/jpeg")


# Pillow format names indexed by the extensions we emit. Used by
# safe_save_image to AVOID inferring format-from-extension at the PIL layer
# (since that's what caused the demotion-to-JPEG bug class in the first place).
_FORMAT_FROM_EXT = {
    ".jpg":  "JPEG",
    ".jpeg": "JPEG",
    ".png":  "PNG",
    ".webp": "WEBP",
    ".gif":  "GIF",
    ".bmp":  "BMP",
    ".tif":  "TIFF",
    ".tiff": "TIFF",
}

# Formats that can carry an embedded ICC profile.
_ICC_CAPABLE = {"JPEG", "PNG", "WEBP", "TIFF"}
# Formats that can carry EXIF.
_EXIF_CAPABLE = {"JPEG", "WEBP", "TIFF"}
# Formats with no alpha channel.
_NO_ALPHA = {"JPEG", "BMP"}


def safe_save_image(img, dst, source_info: Optional[Dict[str, Any]] = None,
                    output_format: Optional[str] = None) -> str:
    """Save a PIL image to `dst`, preserving ICC/EXIF when the target format
    supports it and only coercing mode (RGBA→RGB) when the format demands it.

    Returns the resolved Pillow format name (e.g. "PNG", "JPEG").

    Order of precedence for format:
      1. Explicit `output_format` argument (already a Pillow name)
      2. `dst` suffix mapped via _FORMAT_FROM_EXT
      3. Fallback "JPEG"
    """
    dst = Path(dst)
    if output_format:
        fmt = output_format.upper()
    else:
        fmt = _FORMAT_FROM_EXT.get(dst.suffix.lower(), "JPEG")

    save_kwargs: Dict[str, Any] = {}

    if source_info:
        icc = source_info.get("icc_profile")
        if icc and fmt in _ICC_CAPABLE:
            save_kwargs["icc_profile"] = icc
        exif = source_info.get("exif")
        if exif and fmt in _EXIF_CAPABLE:
            save_kwargs["exif"] = exif

    # JPEG/BMP can't carry alpha; coerce only for those targets.
    if fmt in _NO_ALPHA and img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    if fmt == "JPEG":
        save_kwargs.setdefault("quality", 95)

    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, format=fmt, **save_kwargs)
    return fmt


# Google API key shape: "AIza" + 35 chars of base64url-ish material = 39 total.
# Match the family so we can scrub it from any text we surface to users —
# error messages especially, since Gemini 401/403 bodies sometimes echo the
# rejected credential. We're conservative here: anything that LOOKS like a
# key gets replaced, even if it turns out to be a coincidental run of chars.
_API_KEY_PATTERN = re.compile(r"AIza[A-Za-z0-9_\-]{35}")


def redact_api_key(s: str) -> str:
    """Replace any Google API-key-shaped substring with `<redacted-api-key>`.
    Use on any text (esp. response bodies) before surfacing it to the user."""
    if not s:
        return s
    return _API_KEY_PATTERN.sub("<redacted-api-key>", s)


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
