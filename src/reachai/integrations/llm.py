from __future__ import annotations

import os
from typing import Any, Dict

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class LLMClient:
    """OpenRouter-compatible LLM client using OpenAI SDK."""
    
    def __init__(self, api_key: str | None = None, model: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "openrouter/meta-llama/llama-2-70b-chat")
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.client = None
        
        if OPENAI_AVAILABLE and self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )

    def generate(self, prompt: str) -> Dict[str, Any]:
        """Generate LLM response via OpenRouter."""
        if not self.client:
            # Fallback if OpenAI SDK not installed
            return self._mock_response()
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional outreach assistant. Return JSON responses."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content
            # Parse as JSON if possible, otherwise return structured response
            try:
                import json
                return json.loads(content)
            except:
                return {
                    "should_contact": True,
                    "channel": "email",
                    "message": content,
                    "confidence": 0.8,
                }
        except Exception as e:
            print(f"LLM generation error: {e}")
            return self._mock_response()
    
    def _mock_response(self) -> Dict[str, Any]:
        """Fallback mock response for testing."""
        return {
            "should_contact": True,
            "channel": "email",
            "subject": "AI Engineer opportunity",
            "message": "Hi there, I would love to connect and share my resume.",
            "confidence": 0.9,
        }
