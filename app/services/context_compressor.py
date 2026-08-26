"""上下文压缩服务"""

from typing import List
from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage, SystemMessage)
from langgraph.checkpoint.base import ChannelVersions, empty_checkpoint
from loguru import logger
from app.config import config
from app.core.llm_factory import llm_factory

SUMMARY_PROMPT = """请将以下对话历史压缩为简洁的摘要。要求：保留关键问题和重要回答，丢弃无关内容，使用第三人称描述。"""


class ContextCompressor:
    def __init__(self):
        self.enabled = config.context_compression_enabled
        self.threshold = config.context_compression_threshold
        self.keep_recent = config.context_compression_keep_recent
        self.window_size = config.context_window_size
        logger.info(f"上下文压缩服务初始化完成: enabled={self.enabled}, threshold={self.threshold}")

    async def compress_if_needed(self, checkpointer, session_id: str) -> bool:
        if not self.enabled:
            return False
        try:
            config_dict = {"configurable": {"thread_id": session_id, "checkpoint_ns": ""}}
            checkpoint = await checkpointer.aget(config_dict)
            if not checkpoint:
                return False
            messages = checkpoint.get("channel_values", {}).get("messages", [])
            if not messages:
                return False
            total_tokens = self._estimate_tokens(messages)
            threshold_tokens = int(self.window_size * self.threshold)
            if total_tokens <= threshold_tokens:
                return False
            logger.info(f"[会话 {session_id}] 触发上下文压缩: {total_tokens} tokens > {threshold_tokens} 阈值")
            await self._compress_messages(checkpointer, session_id, config_dict, messages)
            return True
        except Exception as e:
            logger.error(f"[会话 {session_id}] 上下文压缩失败: {e}")
            return False

    async def _compress_messages(self, checkpointer, session_id: str, config_dict: dict, messages: List[BaseMessage]):
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        other_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
        if len(other_msgs) <= self.keep_recent:
            return
        compress_area = other_msgs[:-self.keep_recent]
        keep_area = other_msgs[-self.keep_recent:]
        summary = await self._generate_summary(compress_area)
        new_messages = []
        if system_msgs:
            new_messages.extend(system_msgs)
        new_messages.append(HumanMessage(content=f"[历史对话摘要]\n{summary}"))
        new_messages.extend(keep_area)
        await checkpointer.adelete_thread(session_id)
        new_checkpoint = empty_checkpoint()
        new_checkpoint["channel_values"] = {"messages": new_messages}
        version = str(len(new_messages))
        new_checkpoint["channel_versions"] = {"messages": version}
        await checkpointer.aput(config_dict, new_checkpoint, {}, ChannelVersions({"messages": version}))
        logger.info(f"[会话 {session_id}] 压缩完成: {len(messages)} 条 -> {len(new_messages)} 条")

    async def _generate_summary(self, messages: List[BaseMessage]) -> str:
        formatted_parts = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                continue
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            content = msg.content if hasattr(msg, "content") else str(msg)
            if len(content) > 800:
                content = content[:800] + "...(已截断)"
            formatted_parts.append(f"[{role}]: {content}")
        formatted_text = "\n".join(formatted_parts)
        llm = llm_factory.get_agent_llm()
        response = await llm.ainvoke([SystemMessage(content=SUMMARY_PROMPT), HumanMessage(content=f"请压缩以下对话历史：\n\n{formatted_text}")])
        return response.content if hasattr(response, "content") else str(response)

    def _estimate_tokens(self, messages: List[BaseMessage]) -> int:
        total = 0
        for msg in messages:
            content = msg.content if hasattr(msg, "content") else str(msg)
            total += max(1, len(content) // 4)
            total += 4
        return total


context_compressor = ContextCompressor()