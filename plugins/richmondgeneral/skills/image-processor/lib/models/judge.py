import os
import base64
import json
import requests
from typing import List, Optional, Tuple
from pathlib import Path

class AgentJudge:
    """An LLM-as-a-judge to evaluate generated images against an original for faithfulness."""
    
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    MODEL = "gemini-2.5-pro"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required for the AgentJudge.")
            
    def _encode_image(self, path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
            
    def _get_mime_type(self, path: str) -> str:
        ext = Path(path).suffix.lower()
        if ext in ['.png']: return 'image/png'
        if ext in ['.webp']: return 'image/webp'
        return 'image/jpeg'
        
    def evaluate_candidates(self, original_path: str, candidate_paths: List[str]) -> Tuple[Optional[int], str]:
        """
        Evaluates candidate images against the original.
        Returns (best_index, reasoning_log). best_index is 0-indexed relative to candidate_paths list.
        """
        parts = []
        
        # Add original image
        parts.append({"text": "Image 0: ORIGINAL"})
        parts.append({
            "inline_data": {
                "mime_type": self._get_mime_type(original_path),
                "data": self._encode_image(original_path)
            }
        })
        
        # Add candidates
        for i, cand_path in enumerate(candidate_paths):
            parts.append({"text": f"Image {i+1}: CANDIDATE {i+1}"})
            parts.append({
                "inline_data": {
                    "mime_type": self._get_mime_type(cand_path),
                    "data": self._encode_image(cand_path)
                }
            })
            
        prompt = f"""
You are an expert catalog reviewer. I have provided an ORIGINAL product photo, followed by {len(candidate_paths)} CANDIDATE photos.
The candidates are supposed to have the background removed, but the generative model sometimes hallucinates.

Your task is to evaluate each CANDIDATE against the ORIGINAL. 
CRITICAL FAILURE CRITERIA:
1. Hallucinated Text: The candidate invents legible text, logos, or maker's marks that are illegible, blank, or different in the ORIGINAL.
2. Altered Composition: The candidate restages the items, changes the perspective (e.g. oblique to top-down), or reshapes the objects.
3. Background Fails: The background is not removed cleanly.

You must be extremely strict. If a candidate alters the object's physical appearance or adds fake text, it MUST be rejected.

Respond strictly with a JSON object matching this structure:
{{
  "evaluations": [
    {{"candidate_index": 1, "reasoning": "...", "is_acceptable": true/false}},
    ...
  ],
  "best_candidate_index": <integer or null if none are acceptable>
}}
"""
        parts.append({"text": prompt})
        
        url = f"{self.BASE_URL}/models/{self.MODEL}:generateContent"
        headers = {"x-goog-api-key": self.api_key}
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            parsed = json.loads(text_response)
            
            best_idx = parsed.get("best_candidate_index")
            if best_idx is not None:
                # adjust from 1-indexed (prompt) to 0-indexed (python array)
                best_idx = int(best_idx) - 1
                if best_idx < 0 or best_idx >= len(candidate_paths):
                    best_idx = None
                    
            return best_idx, json.dumps(parsed, indent=2)
            
        except Exception as e:
            return None, f"Judge failed or crashed: {str(e)}"
