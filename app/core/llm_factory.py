"""LLM 工厂类

使用 ChatQwen 调用阿里云 DashScope 通义千问模型。
"""

from typing import Dict, Tuple
from langchain_qwq import ChatQwen
from app.config import config
from loguru import logger


class LLMFactory:
    """LLM 工厂类 - 单例缓存，避免重复创建"""

    _cache: Dict[Tuple[str, float, bool], ChatQwen] = {}

    @staticmethod
    def create_chat_model(
        model: str | None = None,
        temperature: float = 0.7,
        streaming: bool = False,
    ) -> ChatQwen:
        """创建或获取缓存的 ChatQwen 实例"""
        model = model or config.rag_model
        cache_key = (model, temperature, streaming)

        if cache_key not in LLMFactory._cache:
            llm = ChatQwen(
                model=model,
                api_key=config.dashscope_api_key,
                temperature=temperature,
                streaming=streaming,
            )
            LLMFactory._cache[cache_key] = llm
            logger.info(f"创建 LLM 实例: model={model}, temp={temperature}, streaming={streaming}")

        return LLMFactory._cache[cache_key]

    @classmethod
    def get_agent_llm(cls, model: str | None = None) -> ChatQwen:
        """获取 Agent 使用的 LLM (temperature=0, 非流式)"""
        return cls.create_chat_model(model=model, temperature=0, streaming=False)

    @classmethod
    def get_chat_llm(cls, model: str | None = None) -> ChatQwen:
        """获取对话使用的 LLM (temperature=0.7, 流式)"""
        return cls.create_chat_model(model=model, temperature=0.7, streaming=True)


llm_factory = LLMFactory()