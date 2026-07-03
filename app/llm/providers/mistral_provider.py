"""
app/llm/providers/mistral_provider.py
Mistral AI LLM provider via OpenAI-compatible endpoint.
Free "Experiment" tier: ~500,000 TPM, ~1B tokens/month.
"""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.llm.providers.base import BaseLLMProvider


class MistralProvider(BaseLLMProvider):

    MISTRAL_BASE_URL = "https://api.mistral.ai/v1"

    def get_model(self, model_name: str, **kwargs) -> BaseChatModel:
        api_key = self.config.MISTRAL_API_KEY
        if not api_key:
            raise ValueError("MISTRAL_API_KEY is not set.")

        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=self.MISTRAL_BASE_URL,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 4096),
        )