"""
app/llm/providers/base.py
Abstract base class for all LLM providers.
"""

from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel

from app.core.logging import get_logger
from app.core.config import get_setting


class BaseLLMProvider(ABC):

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.config = get_setting()

    

    @abstractmethod
    def get_model(self, model_name: str, **kwargs) -> BaseChatModel:
        """
        Return a LangChain-compatible chat model instance.
        Subclasses implement per-provider initialization.
        """
        ...

    def get_model_safe(self, model_name: str, **kwargs) -> BaseChatModel | None:
        """
        Wraps get_model with error handling.
        Returns None on failure so dispatcher can try fallback.
        """
        try:
            model = self.get_model(model_name, **kwargs)
            self.logger.debug(f" model loaded: {model_name}")
            return model
        except Exception as e:
            self.logger.error(f" failed to load '{model_name}': {e}")
            return None