"""
app/llm/dispatcher.py
LLM dispatcher — maps each agent node to its primary and fallback model.
"""


from langchain_core.language_models import BaseChatModel

from app.core.logging import get_logger
from app.llm.providers.groq_provider import GroqProvider
from app.llm.providers.hf_provider import HuggingFaceProvider

from dataclasses import dataclass

@dataclass
class NodeLLMConfig:
    """LLM config for a single node."""
    primary_provider: str        # "groq" | "hf"
    primary_model: str
    fallback_provider: str       # "groq" | "hf"
    fallback_model: str
    temperature: float = 0.3
    max_tokens: int = 4096


#  Node → Model mapping
NODE_CONFIG: dict[str, NodeLLMConfig] = {
    "planner": NodeLLMConfig(
        primary_provider="groq",
        primary_model="llama-3.1-8b-instant",
        fallback_provider="hf",
        fallback_model="Qwen/Qwen2.5-7B-Instruct",
        temperature=0.3,
        max_tokens=2048,
    ),
    "analyzer": NodeLLMConfig(
        primary_provider="hf",
        primary_model="Qwen/Qwen2.5-72B-Instruct",
        fallback_provider="groq",
        fallback_model="llama-3.1-8b-instant",
        temperature=0.2,
        max_tokens=4096,
    ),
    "report": NodeLLMConfig(
        primary_provider="hf",
        primary_model="meta-llama/Llama-3.3-70B-Instruct",
        fallback_provider="groq",
        fallback_model="llama-3.1-8b-instant",
        temperature=0.3,
        max_tokens=4096,
    ),
}


class LLMDispatcher:
    """
    Returns the correct LangChain chat model for each node.
    Tries primary provider first — falls back automatically on failure.
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self._providers = {
            "groq": GroqProvider(),
            "hf": HuggingFaceProvider(),
        }

    def get_llm(self, node_name: str) -> BaseChatModel:
        """
        Returns a ready-to-use LangChain chat model for the given node.
        Raises RuntimeError if both primary and fallback fail.
        """
        config = NODE_CONFIG.get(node_name)
        if not config:
            raise ValueError(f"No LLM config found for node: '{node_name}'")

        kwargs = {
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }

        # Try primary
        primary = self._providers[config.primary_provider]
        model = primary.get_model_safe(config.primary_model, **kwargs)
        if model:
            self.logger.info(
                f"[{node_name}] using {config.primary_provider} "
                f"→ {config.primary_model}"
            )
            return model

        # Try fallback
        self.logger.warning(
            f"[{node_name}] primary failed, trying fallback: "
            f"{config.fallback_provider} → {config.fallback_model}"
        )
        fallback = self._providers[config.fallback_provider]
        model = fallback.get_model_safe(config.fallback_model, **kwargs)
        if model:
            return model

        raise RuntimeError(
            f"[{node_name}] both primary ({config.primary_provider}/{config.primary_model}) "
            f"and fallback ({config.fallback_provider}/{config.fallback_model}) failed."
        )