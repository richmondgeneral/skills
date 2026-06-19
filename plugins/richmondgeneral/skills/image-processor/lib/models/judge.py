import os
import pydantic
import asyncio
import json
from typing import List, Optional, Tuple

from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.types import Image

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
        
        # Configure the agent
        prompt = """You are an expert catalog reviewer. I have provided an ORIGINAL product photo, followed by CANDIDATE photos.
The candidates are supposed to have the background removed, but the generative model sometimes hallucinates.

Your task is to evaluate each CANDIDATE against the ORIGINAL. 
CRITICAL FAILURE CRITERIA:
1. Hallucinated Text: The candidate invents legible text, logos, or maker's marks that are illegible, blank, or different in the ORIGINAL.
2. Altered Composition: The candidate restages the items, changes the perspective (e.g. oblique to top-down), or reshapes the objects.
3. Background Fails: The background is not removed cleanly.

You must be extremely strict. If a candidate alters the object's physical appearance or adds fake text, it MUST be rejected.
The best candidate index should be 0-indexed relative to the candidate images provided. If no candidates are acceptable, return null.
"""
        os.environ["GEMINI_API_KEY"] = self.api_key # Antigravity will pick this up automatically
        self.config = LocalAgentConfig(
            model="gemini-2.5-pro",
            system_instructions=prompt,
            response_schema=JudgeResult,
        )

    def evaluate_candidates(self, original_path: str, candidate_paths: List[str]) -> Tuple[Optional[int], str]:
        """
        Evaluates candidate images against the original.
        Returns (best_index, reasoning_log). best_index is 0-indexed relative to candidate_paths list.
        """
        # Antigravity agents are async, so we wrap the call.
        return asyncio.run(self._evaluate_async(original_path, candidate_paths))
        
    async def _evaluate_async(self, original_path: str, candidate_paths: List[str]) -> Tuple[Optional[int], str]:
        payload = ["ORIGINAL:"]
        payload.append(Image.from_file(original_path))
        
        for i, cand_path in enumerate(candidate_paths):
            payload.append(f"CANDIDATE {i}:")
            payload.append(Image.from_file(cand_path))
            
        async with Agent(self.config) as agent:
            try:
                response = await agent.chat(payload)
                data = await response.structured_output()
                
                if not data:
                    return None, "Failed to parse structured output."
                
                # data is a dict because response.structured_output() returns a dict, 
                # so we can parse it into our pydantic model to be safe or just use it directly.
                parsed_data = JudgeResult.model_validate(data)
                reasoning = parsed_data.model_dump_json(indent=2)
                best_idx = parsed_data.best_candidate_index
                
                if best_idx is not None and (best_idx < 0 or best_idx >= len(candidate_paths)):
                    best_idx = None
                    
                return best_idx, reasoning
            except Exception as e:
                return None, f"Judge failed: {str(e)}"
