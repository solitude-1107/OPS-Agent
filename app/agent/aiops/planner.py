"""
Planner 节点：制定执行计划
"""

from textwrap import dedent
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from loguru import logger

from app.config import config
from app.core.llm_factory import llm_factory
from app.tools import DEFAULT_LOCAL_AGENT_TOOLS, retrieve_knowledge
from app.agent.mcp_client import get_cached_mcp_tools
from .state import PlanExecuteState
from .utils import format_tools_description


class Plan(BaseModel):
    steps: List[str] = Field(description="完成任务所需的不同步骤")


planner_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            dedent("""
                作为一个专家级别的规划者，你需要将复杂的任务分解为可执行的步骤。

                可用工具列表（用于制定计划时参考）：

                {tools_description}

                注意：你的职责是制定计划，实际的工具调用由 Executor 负责执行。

                {experience_context}

                对于给定的任务，请创建一个简单的、逐步的计划来完成它。计划应该：
                - 将任务分解为逻辑上独立的步骤
                - 每个步骤应该明确使用哪些工具来获取信息
                - 步骤之间应该有清晰的依赖关系
                - 步骤描述要具体、可操作
                - **如果有相关经验文档，请参考其中的方法和步骤制定计划**
            """).strip(),
        ),
        ("placeholder", "{messages}"),
    ]
)


async def planner(state: PlanExecuteState) -> Dict[str, Any]:
    logger.info("=== Planner：制定执行计划 ===")
    input_text = state.get("input", "")
    logger.info(f"用户输入: {input_text}")

    try:
        logger.info("查询内部文档，寻找相关经验...")
        experience_docs = ""
        try:
            context_str = await retrieve_knowledge.ainvoke({"query": input_text})
            if context_str and context_str.strip():
                experience_docs = context_str
                logger.info(f"找到相关经验文档，长度: {len(experience_docs)}")
            else:
                logger.info("未找到相关经验文档")
        except Exception as e:
            logger.warning(f"查询内部文档失败: {e}")

        local_tools = list(DEFAULT_LOCAL_AGENT_TOOLS)
        mcp_tools = await get_cached_mcp_tools()
        all_tools = local_tools + mcp_tools
        logger.info(f"可用工具数量: 本地 {len(local_tools)} + MCP {len(mcp_tools)}")
        tools_description = format_tools_description(all_tools)

        if experience_docs:
            experience_context = f"## 相关经验文档\n\n{experience_docs}\n\n---"
        else:
            experience_context = ""

        llm = llm_factory.get_agent_llm()
        planner_chain = planner_prompt | llm.with_structured_output(Plan)

        plan_result = await planner_chain.ainvoke({
            "messages": [("user", input_text)],
            "tools_description": tools_description,
            "experience_context": experience_context
        })

        if isinstance(plan_result, Plan):
            plan_steps = plan_result.steps
        else:
            plan_steps = plan_result.get("steps", [])

        logger.info(f"计划已生成，共 {len(plan_steps)} 个步骤")
        for i, step in enumerate(plan_steps, 1):
            logger.info(f"  步骤{i}: {step}")

        return {"plan": plan_steps}

    except Exception as e:
        logger.error(f"生成计划失败: {e}", exc_info=True)
        return {"plan": ["收集相关信息", "分析数据", "生成报告"]}
