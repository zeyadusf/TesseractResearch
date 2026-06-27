"""
app/llm/providers/hf_provider.py
HuggingFace LLM provider via OpenAI-compatible inference endpoint.
Uses langchain-openai with HuggingFace router base URL.
"""

import os

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.llm.providers.base import BaseLLMProvider


class HuggingFaceProvider(BaseLLMProvider):

    HF_BASE_URL = "https://router.huggingface.co/v1"

    def get_model(self, model_name: str, **kwargs) -> BaseChatModel:
        api_key = self.config.HUGGINGFACEHUB_API_TOKEN
        if not api_key:
            raise ValueError("HUGGINGFACEHUB_API_TOKEN is not set.")

        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=self.HF_BASE_URL,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 4096),
        )