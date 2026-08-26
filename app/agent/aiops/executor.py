"""
Executor 节点：执行单个步骤
"""

from textwrap import dedent
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import ToolNode
from loguru import logger

from app.config import config
from app.core.llm_factory import llm_factory
from app.tools import DEFAULT_LOCAL_AGENT_TOOLS
from app.agent.mcp_client import get_cached_mcp_tools
from .state import PlanExecuteState


EXECUTOR_SYSTEM_PROMPT = dedent("""
    你是一个能力强大的助手，负责执行具体的任务步骤。
    你可以使用各种工具来完成任务。对于每个步骤：
    1. 理解步骤的目标
    2. 选择合适的工具，如果已经指定了工具，则使用指定的工具
    3. 调用工具获取信息
    4. 返回执行结果

    注意：
    - 如果工具调用失败，请说明失败原因
    - 不要编造数据，只返回实际获取的信息
    - 执行结果要清晰、准确
    - 专注于当前步骤，不要考虑其他任务
""").strip()

RESPONSE_SYSTEM_PROMPT = dedent("""
    根据工具返回的原始数据，生成清晰、简洁的执行结果摘要。
    要求：
    - 提取关键信息，不要遗漏重要数据
    - 使用自然语言描述，便于后续步骤参考
    - 如果工具返回了告警信息，明确指出告警状态
    - 如果工具调用失败，说明失败原因
    - 不要编造数据，只基于工具实际返回的内容总结
""").strip()


async def executor(state: PlanExecuteState) -> Dict[str, Any]:
    logger.info("=== Executor：执行步骤 ===")
    plan = state.get("plan", [])
    if not plan:
        logger.info("计划为空，跳过执行")
        return {}

    task = plan[0]
    logger.info(f"当前任务: {task}")

    try:
        local_tools = list(DEFAULT_LOCAL_AGENT_TOOLS)
        mcp_tools = await get_cached_mcp_tools()
        logger.info(f"可用工具数量: 本地 {len(local_tools)} + MCP {len(mcp_tools)}")
        all_tools = local_tools + mcp_tools

        llm = llm_factory.get_agent_llm()
        llm_with_tools = llm.bind_tools(all_tools)
        tool_node = ToolNode(all_tools)

        messages = [
            SystemMessage(content=EXECUTOR_SYSTEM_PROMPT),
            HumanMessage(content=f"请执行以下任务: {task}")
        ]

        llm_response = await llm_with_tools.ainvoke(messages)
        logger.info(f"LLM 响应类型: {type(llm_response)}")

        if hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
            logger.info(f"检测到 {len(llm_response.tool_calls)} 个工具调用")
            messages.append(llm_response)
            tool_messages = await tool_node.ainvoke({"messages": messages})

            tool_result_content = "\n\n".join(
                msg.content for msg in tool_messages["messages"]
                if hasattr(msg, "content")
            )

            summary_chain = ChatPromptTemplate.from_messages([
                ("system", RESPONSE_SYSTEM_PROMPT),
                ("human", "任务: {task}\n\n工具返回的原始数据:\n{tool_result}\n\n请生成执行结果摘要:")
            ]) | llm

            summary_response = await summary_chain.ainvoke({
                "task": task,
                "tool_result": tool_result_content[:3000]
            })
            result = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)
        else:
            logger.info("LLM 未调用工具，直接返回结果")
            result = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)

        logger.info(f"步骤执行完成，结果长度: {len(result)}")
        return {
            "plan": plan[1:],
            "past_steps": [(task, result)],
        }

    except Exception as e:
        logger.error(f"执行步骤失败: {e}", exc_info=True)
        return {
            "plan": plan[1:],
            "past_steps": [(task, f"执行失败: {str(e)}")],
        }
