from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from config import (AgentConfig, AnthropicConfig, ConfigParser, OllamaConfig,
                    OpenAIConfig)

ProviderRegistry: dict[str, BaseChatModel] = {}

openai_config = ConfigParser.get(OpenAIConfig)
ProviderRegistry["openai"] = ChatOpenAI(
    model_name=openai_config.model,
    temperature=openai_config.temperature,
    max_tokens=openai_config.max_tokens,
    openai_api_key=openai_config.api_key,
    organization=openai_config.organization_id,
    request_timeout=openai_config.timeout,
)

anthropic_config = ConfigParser.get(AnthropicConfig)
ProviderRegistry["anthropic"] = ChatAnthropic(
    model=anthropic_config.model,
    temperature=anthropic_config.temperature,
    max_tokens=anthropic_config.max_tokens,
    anthropic_api_key=anthropic_config.api_key,
    request_timeout=anthropic_config.timeout,
)

ollama_config = ConfigParser.get(OllamaConfig)
ProviderRegistry["ollama"] = ChatOllama(
    model=ollama_config.model,
    temperature=ollama_config.temperature,
    max_tokens=ollama_config.max_tokens,
    base_url=ollama_config.base_url,
    keep_alive=ollama_config.keep_alive
)

agent_base_config = ConfigParser.get(AgentConfig)
LLM = ProviderRegistry.get(agent_base_config.default_provider)

if not LLM:
    raise ValueError(f"Unsupported provider type: {agent_base_config.default_provider}")
__all__ = ["ProviderRegistry", "LLM"]