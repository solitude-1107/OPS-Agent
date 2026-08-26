"""RAG Agent 服务 - 基于 LangGraph 的智能代理"""

from typing import Annotated, Any, AsyncGenerator, Dict, Sequence
from langchain.agents import create_agent
from langchain_core.messages import (BaseMessage, HumanMessage, RemoveMessage, SystemMessage)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from loguru import logger
from typing_extensions import TypedDict
from app.config import config
from app.services.context_compressor import context_compressor
from app.core.llm_factory import llm_factory
from app.tools import DEFAULT_LOCAL_AGENT_TOOLS
from app.agent.mcp_client import (get_cached_mcp_tools, format_exception_chain, suggest_mcp_transport)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


def trim_messages_middleware(state: AgentState) -> dict[str, Any] | None:
    messages = state["messages"]
    if len(messages) <= 7:
        return None
    first_msg = messages[0]
    recent_messages = messages[-6:] if len(messages) % 2 == 0 else messages[-7:]
    new_messages = [first_msg] + list(recent_messages)
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *new_messages]}


class RagAgentService:
    def __init__(self, streaming: bool = True):
        self.model_name = config.rag_model
        self.streaming = streaming
        self.system_prompt = self._build_system_prompt()
        self.model = llm_factory.get_chat_llm()
        self.tools = list(DEFAULT_LOCAL_AGENT_TOOLS)
        self.mcp_tools: list = []
        self.checkpointer = None
        self.agent = None
        self._agent_initialized = False
        logger.info(f"RAG Agent 服务初始化完成 (ChatQwen), model={self.model_name}")

    async def _initialize_agent(self):
        if self._agent_initialized:
            return
        if self.checkpointer is None:
            self.checkpointer = AsyncSqliteSaver.from_conn_string("data/conversations.db")
            await self.checkpointer.setup()
        for name, server in config.mcp_servers.items():
            hint = suggest_mcp_transport(str(server.get("url", "")), str(server.get("transport", "")))
            if hint:
                logger.warning(f"MCP 配置 [{name}]: {hint}")
        mcp_tools = await get_cached_mcp_tools()
        if not mcp_tools:
            logger.warning("MCP 工具加载失败，将仅使用本地工具继续运行")
            self.mcp_tools = []
        else:
            self.mcp_tools = mcp_tools
        all_tools = self.tools + self.mcp_tools
        self.agent = create_agent(self.model, tools=all_tools, checkpointer=self.checkpointer)
        self._agent_initialized = True
        if all_tools:
            tool_names = [tool.name if hasattr(tool, "name") else str(tool) for tool in all_tools]
            logger.info(f"可用工具列表: {', '.join(tool_names)}")

    def _build_system_prompt(self) -> str:
        from textwrap import dedent
        return dedent("""
            你是一个专业的AI助手，能够使用多种工具来帮助用户解决问题。
            工作原则:
            1. 理解用户需求，选择合适的工具来完成任务
            2. 当需要获取实时信息或专业知识时，主动使用相关工具
            3. 基于工具返回的结果提供准确、专业的回答
            4. 如果工具无法提供足够信息，请诚实地告知用户
            回答要求:
            - 保持友好、专业的语气
            - 回答简洁明了，重点突出
            - 基于事实，不编造信息
        """).strip()

    async def query(self, question: str, session_id: str) -> str:
        try:
            await self._initialize_agent()
            logger.info(f"[会话 {session_id}] RAG Agent 收到查询（非流式）: {question}")
            await context_compressor.compress_if_needed(self.checkpointer, session_id)
            messages = [SystemMessage(content=self.system_prompt), HumanMessage(content=question)]
            agent_input = {"messages": messages}
            config_dict = {"configurable": {"thread_id": session_id}}
            result = await self.agent.ainvoke(input=agent_input, config=config_dict)
            messages_result = result.get("messages", [])
            if messages_result:
                last_message = messages_result[-1]
                answer = last_message.content if hasattr(last_message, 'content') else str(last_message)
                logger.info(f"[会话 {session_id}] RAG Agent 查询完成（非流式）")
                return answer
            return ""
        except Exception as e:
            logger.error(f"[会话 {session_id}] RAG Agent 查询失败: {format_exception_chain(e)}")
            raise

    async def query_stream(self, question: str, session_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            await self._initialize_agent()
            logger.info(f"[会话 {session_id}] RAG Agent 收到查询（流式）: {question}")
            await context_compressor.compress_if_needed(self.checkpointer, session_id)
            messages = [SystemMessage(content=self.system_prompt), HumanMessage(content=question)]
            agent_input = {"messages": messages}
            config_dict = {"configurable": {"thread_id": session_id}}
            async for token, metadata in self.agent.astream(input=agent_input, config=config_dict, stream_mode="messages"):
                node_name = metadata.get('langgraph_node', 'unknown') if isinstance(metadata, dict) else 'unknown'
                message_type = type(token).__name__
                if message_type in ("AIMessage", "AIMessageChunk"):
                    content_blocks = getattr(token, 'content_blocks', None)
                    if content_blocks and isinstance(content_blocks, list):
                        for block in content_blocks:
                            if isinstance(block, dict) and block.get('type') == 'text':
                                text_content = block.get('text', '')
                                if text_content:
                                    yield {"type": "content", "data": text_content, "node": node_name}
            logger.info(f"[会话 {session_id}] RAG Agent 查询完成（流式）")
            yield {"type": "complete"}
        except Exception as e:
            detail = format_exception_chain(e)
            logger.error(f"[会话 {session_id}] RAG Agent 查询失败（流式）: {detail}")
            yield {"type": "error", "data": detail}

    def get_session_history(self, session_id: str) -> list:
        try:
            config = {"configurable": {"thread_id": session_id}}
            checkpoint_tuple = self.checkpointer.get(config)
            if not checkpoint_tuple:
                return []
            if hasattr(checkpoint_tuple, 'checkpoint'):
                checkpoint_data = checkpoint_tuple.checkpoint
            else:
                checkpoint_data = checkpoint_tuple[0] if checkpoint_tuple else {}
            messages = checkpoint_data.get("channel_values", {}).get("messages", [])
            history = []
            for msg in messages:
                if isinstance(msg, SystemMessage):
                    continue
                role = "user" if isinstance(msg, HumanMessage) else "assistant"
                content = msg.content if hasattr(msg, 'content') else str(msg)
                from datetime import datetime
                history.append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
            return history
        except Exception as e:
            logger.error(f"获取会话历史失败: {session_id}, 错误: {e}")
            return []

    def clear_session(self, session_id: str) -> bool:
        try:
            self.checkpointer.delete_thread(session_id)
            return True
        except Exception as e:
            logger.error(f"清空会话历史失败: {session_id}, 错误: {e}")
            return False

    async def cleanup(self):
        try:
            if self.checkpointer is not None:
                await self.checkpointer.conn.close()
        except Exception as e:
            logger.error(f"清理资源失败: {e}")


rag_agent_service = RagAgentService(streaming=True)