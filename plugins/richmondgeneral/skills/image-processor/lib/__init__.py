"""Image processor library."""
# Resolve API keys (existing env -> macOS Keychain -> workspace .env) before any
# model is constructed, so clean.py works over the bare mac-bridge shell where
# ~/.zshrc never ran to export GEMINI_API_KEY / NANO_BANANA_API_KEY.
from .env import bootstrap_keys as _bootstrap_keys
_bootstrap_keys()

from .models import (
    BaseModel,
    ProcessingResult,
    TaskConfig,
    TaskType,
    NanaBananaModel,
    Gemini25FlashModel,
    RemoveBgModel,
    GeminiImageModel,
    GeminiAPIError,
)
from .router import ModelRouter, create_default_router

__all__ = [
    # Models
    'BaseModel',
    'ProcessingResult',
    'TaskConfig',
    'TaskType',
    'NanaBananaModel',
    'Gemini25FlashModel',
    'RemoveBgModel',
    'GeminiImageModel',
    'GeminiAPIError',
    # Router
    'ModelRouter',
    'create_default_router',
]
