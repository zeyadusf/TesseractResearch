"""
app/llm/providers/groq_provider.py
Groq LLM provider via langchain-groq.
"""

from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq

from app.llm.providers.base import BaseLLMProvider


class GroqProvider(BaseLLMProvider):


    def get_model(self, model_name: str, **kwargs) -> BaseChatModel:
        api_key = self.config.GROQ_API_KEY
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set.")

        return ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=kwargs.get("temperature", 0.3),
            max_tokens=kwargs.get("max_tokens", 4096),
        )