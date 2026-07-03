"""
app/llm/dispatcher.py
LLM dispatcher — maps each agent node to its primary model and an ordered
fallback chain.

FIX: ChatOpenAI() never fails at construction time (no network call happens
until .invoke()/.ainvoke()). get_model_safe()-style construction guards never
catch a runtime 401/402/403/413/5xx from the provider during the actual call.
ainvoke_with_fallback() tries primary, then walks the fallback chain in
order on any exception, so a single depleted/rate-limited provider doesn't
take a node down when other providers are configured.
"""

from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel

from app.core.logging import get_logger
from app.llm.providers.groq_provider import GroqProvider
from app.llm.providers.hf_provider import HuggingFaceProvider
from app.llm.providers.cerebras_provider import CerebrasProvider
from app.llm.providers.mistral_provider import MistralProvider


@dataclass
class FallbackStep:
    provider: str   # "groq" | "hf" | "cerebras" | "mistral"
    model: str


@dataclass
class NodeLLMConfig:
    """LLM config for a single node: one primary, ordered fallback chain."""
    primary_provider: str
    primary_model: str
    fallbacks: list[FallbackStep] = field(default_factory=list)
    temperature: float = 0.3
    max_tokens: int = 4096


NODE_CONFIG: dict[str, NodeLLMConfig] = {
    "planner": NodeLLMConfig(
        primary_provider="groq",
        primary_model="llama-3.1-8b-instant",
        fallbacks=[
            FallbackStep("cerebras", "gpt-oss-120b"),
            FallbackStep("hf", "Qwen/Qwen2.5-7B-Instruct"),
        ],
        temperature=0.3,
        max_tokens=2048,
    ),
    "analyzer": NodeLLMConfig(
        primary_provider="mistral",
        primary_model="mistral-large-latest",
        fallbacks=[
            FallbackStep("cerebras", "gpt-oss-120b"),
            FallbackStep("hf", "Qwen/Qwen2.5-72B-Instruct"),
            FallbackStep("groq", "llama-3.1-8b-instant"),
        ],
        temperature=0.2,
        max_tokens=4096,
    ),
    "report": NodeLLMConfig(
        primary_provider="hf",
        primary_model="meta-llama/Llama-3.3-70B-Instruct",
        fallbacks=[
            FallbackStep("mistral", "mistral-large-latest"),
            FallbackStep("cerebras", "gpt-oss-120b"),
            FallbackStep("groq", "llama-3.1-8b-instant"),
        ],
        temperature=0.3,
        max_tokens=4096,
    ),
}


class LLMDispatcher:
    """
    Returns LangChain chat models for each node.

    ainvoke_with_fallback() tries the primary model, then each entry in the
    node's fallback chain in order, logging which one actually served the
    request. If a step rejects the request as too large for its rate limit,
    the message is truncated before that step's retry (small free-tier
    providers often have far smaller per-request TPM caps than the primary).
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self._providers = {
            "groq": GroqProvider(),
            "hf": HuggingFaceProvider(),
            "cerebras": CerebrasProvider(),
            "mistral": MistralProvider(),
        }

    def _get_config(self, node_name: str) -> NodeLLMConfig:
        config = NODE_CONFIG.get(node_name)
        if not config:
            raise ValueError(f"No LLM config found for node: '{node_name}'")
        return config

    def get_llm(self, node_name: str) -> BaseChatModel:
        config = self._get_config(node_name)
        kwargs = {"temperature": config.temperature, "max_tokens": config.max_tokens}
        return self._providers[config.primary_provider].get_model(config.primary_model, **kwargs)

    def _build_model(self, provider_name: str, model_name: str, config: NodeLLMConfig) -> BaseChatModel:
        kwargs = {"temperature": config.temperature, "max_tokens": config.max_tokens}
        return self._providers[provider_name].get_model(model_name, **kwargs)

    async def ainvoke_with_fallback(self, node_name: str, messages: list) -> str:
        config = self._get_config(node_name)
        chain = [(config.primary_provider, config.primary_model)] + [
            (step.provider, step.model) for step in config.fallbacks
        ]

        last_exc: Exception | None = None
        for i, (provider_name, model_name) in enumerate(chain):
            model = self._build_model(provider_name, model_name, config)
            label = "primary" if i == 0 else f"fallback[{i}]"
            try:
                response = await model.ainvoke(messages)
                if i > 0:
                    self.logger.warning(
                        f"[{node_name}] served by {label} ({provider_name}/{model_name}) "
                        f"after {i} prior failure(s)"
                    )
                self.logger.debug(f"[{node_name}] used  {label} ({provider_name}/{model_name}) ")
                return response.content.strip()
            except Exception as exc:
                last_exc = exc
                is_too_large = "tokens per minute" in str(exc).lower() or "rate_limit_exceeded" in str(exc).lower()
                if is_too_large:
                    self.logger.warning(
                        f"[{node_name}] {label} ({provider_name}/{model_name}) rejected "
                        f"request as too large; retrying same step with truncated content"
                    )
                    try:
                        truncated = self._truncate_messages(messages, max_chars=12000)
                        response = await model.ainvoke(truncated)
                        return response.content.strip()
                    except Exception as truncated_exc:
                        last_exc = truncated_exc

                self.logger.warning(
                    f"[{node_name}] {label} ({provider_name}/{model_name}) failed: {last_exc}"
                )

        self.logger.error(f"[{node_name}] all providers in chain failed. Last error: {last_exc}")
        raise last_exc

    @staticmethod
    def _truncate_messages(messages: list, max_chars: int) -> list:
        """Truncates the last message's content (the bulky user/context message) to fit a small TPM cap."""
        truncated = list(messages)
        last = truncated[-1]
        content = getattr(last, "content", "")
        if len(content) > max_chars:
            last.content = content[:max_chars] + "\n\n[TRUNCATED FOR FALLBACK MODEL RATE LIMIT]"
        return truncated