#!/usr/bin/env python3
"""
Shared Gemini API Utilities for Agent Skills

Extracted from gemini-chat.py patterns for reusable image generation
and editing operations using Google's Gemini models (Nano Banana).
"""

import os
import sys
import base64
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


class GeminiAPIError(Exception):
    """Base exception for Gemini API errors"""
    pass


class GeminiAPI:
    """
    Gemini API client for image generation and editing operations.
    
    Supports:
    - Text-to-image generation
    - Image-to-image editing
    - Multi-image composition
    - Auto model selection (fast vs pro)
    """
    
    # Model identifiers
    MODEL_FLASH = "gemini-2.5-flash-image"  # Nano Banana (fast)
    MODEL_PRO = "gemini-3-pro-image"         # Nano Banana Pro (quality)
    
    # API configuration
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    TIMEOUT = 60  # seconds
    
    # Supported image formats
    MIME_TYPES = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini API client.
        
        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY env var.
        
        Raises:
            GeminiAPIError: If API key is not found.
        """
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        if not self.api_key:
            raise GeminiAPIError(
                "GEMINI_API_KEY not found. Set environment variable or pass to constructor.\n"
                "Get your key at: https://aistudio.google.com/apikey"
            )
    
    @staticmethod
    def encode_image(image_path: str) -> str:
        """
        Encode image to base64 string.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Base64-encoded image string
            
        Raises:
            FileNotFoundError: If image file doesn't exist
            GeminiAPIError: If encoding fails
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        try:
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            raise GeminiAPIError(f"Failed to encode image: {e}")
    
    @staticmethod
    def get_mime_type(image_path: str) -> str:
        """
        Get MIME type from file extension.
        
        Args:
            image_path: Path to image file
            
        Returns:
            MIME type string (defaults to image/jpeg if unknown)
        """
        ext = Path(image_path).suffix.lower()
        return GeminiAPI.MIME_TYPES.get(ext, 'image/jpeg')
    
    @staticmethod
    def select_model(
        prompt: str,
        reference_images: List[str] = None,
        quality_hint: str = "auto"
    ) -> str:
        """
        Automatically select appropriate model based on task complexity.
        
        Args:
            prompt: Text prompt describing the task
            reference_images: List of reference image paths (if any)
            quality_hint: User preference ("auto", "fast", "pro")
            
        Returns:
            Model identifier (MODEL_FLASH or MODEL_PRO)
        """
        # User override
        if quality_hint == "fast":
            return GeminiAPI.MODEL_FLASH
        elif quality_hint == "pro":
            return GeminiAPI.MODEL_PRO
        
        # Auto-selection heuristics
        num_refs = len(reference_images) if reference_images else 0
        
        # Use pro for complex scenarios
        use_pro = (
            num_refs >= 8 or  # Many reference images
            "4k" in prompt.lower() or
            "high quality" in prompt.lower() or
            "professional" in prompt.lower() or
            "detailed" in prompt.lower() and len(prompt) > 200
        )
        
        return GeminiAPI.MODEL_PRO if use_pro else GeminiAPI.MODEL_FLASH
    
    def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        reference_images: Optional[List[str]] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Generate image from text prompt with optional reference images.
        
        Args:
            prompt: Text description of desired image
            model: Model to use (defaults to MODEL_FLASH)
            reference_images: Optional list of reference image paths
            
        Returns:
            Tuple of (image_bytes, metadata_dict)
            
        Raises:
            GeminiAPIError: If API request fails
        """
        model = model or self.MODEL_FLASH
        
        # Build request parts
        parts = [{"text": prompt}]
        
        # Add reference images if provided
        if reference_images:
            for img_path in reference_images:
                image_data = self.encode_image(img_path)
                mime_type = self.get_mime_type(img_path)
                parts.insert(0, {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_data
                    }
                })
        
        # Make API request
        url = f"{self.BASE_URL}/models/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": parts}]
        }
        
        try:
            response = requests.post(url, json=payload, timeout=self.TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract generated image - check multiple possible response structures
            image_data = None
            
            # Structure 1: candidates[].content.parts[].inlineData (camelCase)
            for candidate in data.get('candidates', []):
                for part in candidate.get('content', {}).get('parts', []):
                    if 'inlineData' in part:
                        image_data = base64.b64decode(part['inlineData']['data'])
                        break
                    # Also try snake_case for backwards compat
                    elif 'inline_data' in part:
                        image_data = base64.b64decode(part['inline_data']['data'])
                        break
                if image_data:
                    break
            
            # Structure 2: candidates[].parts[].inlineData (direct)
            if not image_data:
                for candidate in data.get('candidates', []):
                    for part in candidate.get('parts', []):
                        if 'inlineData' in part:
                            image_data = base64.b64decode(part['inlineData']['data'])
                            break
                        elif 'inline_data' in part:
                            image_data = base64.b64decode(part['inline_data']['data'])
                            break
                    if image_data:
                        break
            
            if not image_data:
                # Debug: print response structure
                import json
                print(f"Debug - API Response: {json.dumps(data, indent=2)[:500]}", file=sys.stderr)
                raise GeminiAPIError("No image data in response")
            
            # Build metadata
            metadata = {
                "model": model,
                "prompt": prompt,
                "reference_count": len(reference_images) if reference_images else 0
            }
            
            return image_data, metadata
            
        except requests.exceptions.Timeout:
            raise GeminiAPIError(f"Request timed out after {self.TIMEOUT}s")
        except requests.exceptions.HTTPError as e:
            error_msg = "Unknown error"
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', str(e))
            except:
                error_msg = str(e)
            raise GeminiAPIError(f"API error: {error_msg}")
        except Exception as e:
            raise GeminiAPIError(f"Unexpected error: {e}")
    
    def edit_image(
        self,
        input_image: str,
        instruction: str,
        model: Optional[str] = None,
        reference_images: Optional[List[str]] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Edit existing image using natural language instructions.
        
        Args:
            input_image: Path to image to edit
            instruction: Natural language editing instruction
            model: Model to use (defaults to MODEL_FLASH)
            reference_images: Optional list of additional reference images
            
        Returns:
            Tuple of (edited_image_bytes, metadata_dict)
            
        Raises:
            GeminiAPIError: If API request fails
        """
        model = model or self.MODEL_FLASH
        
        # Build request - input image first, then instruction
        parts = []
        
        # Add input image
        image_data = self.encode_image(input_image)
        mime_type = self.get_mime_type(input_image)
        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": image_data
            }
        })
        
        # Add reference images if provided
        if reference_images:
            for ref_path in reference_images:
                ref_data = self.encode_image(ref_path)
                ref_mime = self.get_mime_type(ref_path)
                parts.append({
                    "inline_data": {
                        "mime_type": ref_mime,
                        "data": ref_data
                    }
                })
        
        # Add instruction text
        parts.append({"text": instruction})
        
        # Make API request (same as generate_image)
        url = f"{self.BASE_URL}/models/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": parts}]
        }
        
        try:
            response = requests.post(url, json=payload, timeout=self.TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract edited image
            image_data = None
            for candidate in data.get('candidates', []):
                for part in candidate.get('content', {}).get('parts', []):
                    if 'inlineData' in part:
                        image_data = base64.b64decode(part['inlineData']['data'])
                        break
                    elif 'inline_data' in part:
                        image_data = base64.b64decode(part['inline_data']['data'])
                        break
                if image_data:
                    break
            
            if not image_data:
                raise GeminiAPIError("No image data in response")
            
            # Build metadata
            metadata = {
                "model": model,
                "instruction": instruction,
                "input_image": Path(input_image).name,
                "reference_count": len(reference_images) if reference_images else 0
            }
            
            return image_data, metadata
            
        except requests.exceptions.Timeout:
            raise GeminiAPIError(f"Request timed out after {self.TIMEOUT}s")
        except requests.exceptions.HTTPError as e:
            error_msg = "Unknown error"
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', str(e))
            except:
                error_msg = str(e)
            raise GeminiAPIError(f"API error: {error_msg}")
        except Exception as e:
            raise GeminiAPIError(f"Unexpected error: {e}")


def save_image(image_data: bytes, output_path: str) -> None:
    """
    Save image bytes to file.
    
    Args:
        image_data: Image bytes
        output_path: Path to save image
        
    Raises:
        IOError: If save fails
    """
    # Ensure parent directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(output_path, 'wb') as f:
            f.write(image_data)
    except Exception as e:
        raise IOError(f"Failed to save image: {e}")
