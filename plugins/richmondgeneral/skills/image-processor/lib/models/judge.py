import os
import pydantic
from typing import List, Optional, Tuple

from google import genai
from google.genai import types

class Evaluation(pydantic.BaseModel):
    candidate_index: int
    reasoning: str
    is_acceptable: bool

class JudgeResult(pydantic.BaseModel):
    evaluations: list[Evaluation]
    best_candidate_index: int | None

class AgentJudge:
    """An LLM-as-a-judge to evaluate generated images against an original for faithfulness."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required for the AgentJudge.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.5-pro"
        
        self.prompt = """You are an expert catalog reviewer. I have provided an ORIGINAL product photo, followed by CANDIDATE photos.
The candidates are supposed to have the background removed, but the generative model sometimes hallucinates.

Your task is to evaluate each CANDIDATE against the ORIGINAL. 
CRITICAL FAILURE CRITERIA:
1. Hallucinated Text: The candidate invents legible text, logos, or maker's marks that are illegible, blank, or different in the ORIGINAL.
2. Altered Composition: The candidate restages the items, changes the perspective (e.g. oblique to top-down), or reshapes the objects.
3. Background Fails: The background is not removed cleanly.

You must be extremely strict. If a candidate alters the object's physical appearance or adds fake text, it MUST be rejected.
The best candidate index should be 0-indexed relative to the candidate images provided. If no candidates are acceptable, return null.
"""

    def evaluate_candidates(self, original_path: str, candidate_paths: List[str]) -> Tuple[Optional[int], str]:
        from PIL import Image
        
        payload = ["ORIGINAL:"]
        payload.append(Image.open(original_path))
        
        for i, cand_path in enumerate(candidate_paths):
            payload.append(f"CANDIDATE {i}:")
            payload.append(Image.open(cand_path))
            
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=payload,
                config=types.GenerateContentConfig(
                    system_instruction=self.prompt,
                    response_mime_type="application/json",
                    response_schema=JudgeResult,
                    temperature=0.1,
                )
            )
            
            data = response.parsed
            if not data:
                return None, "Failed to parse structured output."
                
            reasoning = data.model_dump_json(indent=2)
            best_idx = data.best_candidate_index
            
            if best_idx is not None and (best_idx < 0 or best_idx >= len(candidate_paths)):
                best_idx = None
                
            return best_idx, reasoning
        except Exception as e:
            return None, f"Judge failed: {str(e)}"
