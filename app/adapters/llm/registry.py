"""LLM 어댑터 타입 → 구현 클래스 매핑.

신규 LLM 추가 방법:
1. app/adapters/llm/<name>_adapter.py 에 LLMAdapter 상속 클래스 작성
2. 아래 _REGISTRY에 추가
"""
from __future__ import annotations

from app.adapters.llm.base import LLMAdapter
from app.adapters.llm.ollama_adapter import OllamaAdapter
from app.adapters.llm.openai_adapter import OpenAIAdapter
from app.core.config import LLMConfig

_REGISTRY: dict[str, type[LLMAdapter]] = {
    "openai": OpenAIAdapter,
    "ollama": OllamaAdapter,
    # "anthropic": AnthropicAdapter,
    # "vllm":      VLLMAdapter,  (vLLM은 OpenAI 호환 endpoint로 OpenAIAdapter 재사용 가능)
}


def supported_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def build_adapter(config: LLMConfig) -> LLMAdapter:
    cls = _REGISTRY.get(config.type)
    if cls is None:
        raise ValueError(
            f"지원하지 않는 LLM 타입입니다: {config.type}. "
            f"adapters/llm/registry.py에 등록 필요."
        )
    return cls(config)
