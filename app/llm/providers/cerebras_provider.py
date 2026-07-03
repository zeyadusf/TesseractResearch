"""
app/llm/providers/cerebras_provider.py
Cerebras LLM provider via OpenAI-compatible endpoint.
Free tier: ~30,000 TPM (much higher than Groq's 6,000 TPM), 1M tokens/day cap.
"""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.llm.providers.base import BaseLLMProvider


class CerebrasProvider(BaseLLMProvider):

    CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"

    def get_model(self, model_name: str, **kwargs) -> BaseChatModel:
        api_key = self.config.CEREBRAS_API_KEY
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY is not set.")

        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=self.CEREBRAS_BASE_URL,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 4096),
        )