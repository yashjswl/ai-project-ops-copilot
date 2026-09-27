"""Provider-agnostic LLM client.

`get_llm_client()` returns whichever backend is configured via
`LLM_PROVIDER` in .env (groq | gemini | ollama). All backends expose the
same `.generate(system_prompt, user_prompt, json_mode=False) -> str`
interface so the rest of the app never needs to know which provider is
behind it — swapping providers is a one-line config change.
"""
import json
from abc import ABC, abstractmethod

import requests

from backend.config import settings


class BaseLLMClient(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        ...


class GroqClient(BaseLLMClient):
    def __init__(self):
        from groq import Groq

        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys")
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    def generate(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **kwargs,
        )
        return resp.choices[0].message.content


class GeminiClient(BaseLLMClient):
    def __init__(self):
        import google.generativeai as genai

        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey")
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._genai = genai
        self.model_name = settings.GEMINI_MODEL

    def generate(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        model = self._genai.GenerativeModel(self.model_name, system_instruction=system_prompt)
        gen_config = {"response_mime_type": "application/json"} if json_mode else {}
        resp = model.generate_content(user_prompt, generation_config=gen_config)
        return resp.text


class OllamaClient(BaseLLMClient):
    def __init__(self):
        self.model = settings.OLLAMA_MODEL
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")

    def generate(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def get_llm_client() -> BaseLLMClient:
    provider = settings.LLM_PROVIDER
    if provider == "groq":
        return GroqClient()
    if provider == "gemini":
        return GeminiClient()
    if provider == "ollama":
        return OllamaClient()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}. Use groq, gemini, or ollama.")


def safe_json_parse(raw: str) -> dict:
    """LLMs sometimes wrap JSON in markdown fences or add stray text — clean before parsing."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
        raise
