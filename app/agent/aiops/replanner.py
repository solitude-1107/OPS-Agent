"""
Replanner 节点：重新规划或生成最终响应
"""

from textwrap import dedent
from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from loguru import logger

from app.config import config
from app.core.llm_factory import llm_factory
from app.tools import DEFAULT_LOCAL_AGENT_TOOLS
from app.agent.mcp_client import get_cached_mcp_tools
from .state import PlanExecuteState
from .utils import format_tools_description


class Response(BaseModel):
    response: str = Field(description="对用户的最终响应")


class Act(BaseModel):
    action: str = Field(description="""下一步的行动，必须是以下三种之一：
        - 'continue': 当前计划合理，继续执行下一个步骤
        - 'replan': 当前计划需要调整，提供新的步骤列表
        - 'respond': 计划已完成且信息充足，生成最终响应""")
    new_steps: List[str] = Field(default_factory=list, description="新的步骤列表")


replanner_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            dedent("""
                作为一个重新规划专家，你需要根据已执行的步骤决定下一步行动。

                可用工具列表：{tools_description}

                你有三个选择（按优先级排序）：

                1. 'respond' - 信息充足，立即生成最终响应（最高优先级）
                2. 'continue' - 当前计划合理，继续执行（次优先级）
                3. 'replan' - 当前计划有严重问题（最低优先级，谨慎使用）

                评估标准：
                - 当前信息是否已经足够解决用户问题？
                - 已执行步骤数是否过多（>= 5）？如果是，立即 respond
            """).strip(),
        ),
        ("placeholder", "{messages}"),
    ]
)

response_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            dedent("""
                根据原始任务和已执行步骤的结果，生成一个全面的最终响应。
                响应要求：清晰、结构化、基于实际数据、使用 Markdown 格式
            """).strip(),
        ),
        ("placeholder", "{messages}"),
    ]
)


async def replanner(state: PlanExecuteState) -> Dict[str, Any]:
    logger.info("=== Replanner：重新规划 ===")
    input_text = state.get("input", "")
    plan = state.get("plan", [])
    past_steps = state.get("past_steps", [])

    logger.info(f"剩余计划步骤: {len(plan)}, 已执行步骤: {len(past_steps)}")

    MAX_STEPS = 8
    if len(past_steps) >= MAX_STEPS:
        logger.warning(f"已执行 {len(past_steps)} 个步骤，超过最大限制，强制生成最终响应")
        return await _generate_response(state, llm_factory.get_agent_llm())

    try:
        local_tools = list(DEFAULT_LOCAL_AGENT_TOOLS)
        mcp_tools = await get_cached_mcp_tools()
        all_tools = local_tools + mcp_tools
        tools_description = format_tools_description(all_tools)
    except Exception as e:
        logger.warning(f"获取工具列表失败: {e}")
        tools_description = "无法获取工具列表"

    llm = llm_factory.get_agent_llm()

    steps_summary = "\n".join([
        f"步骤: {step}\n结果: {result[:300]}..."
        for step, result in past_steps
    ])

    if plan:
        replanner_chain = replanner_prompt | llm.with_structured_output(Act)
        try:
            messages = [
                ("user", f"原始任务: {input_text}"),
                ("user", f"已执行的步骤:\n{steps_summary}"),
                ("user", f"剩余计划: {', '.join(plan)}"),
            ]
            act = await replanner_chain.ainvoke({"messages": messages, "tools_description": tools_description})

            if isinstance(act, Act):
                action = act.action
                new_steps = act.new_steps
            else:
                action = act.get("action", "continue")
                new_steps = act.get("new_steps", [])

            logger.info(f"Replanner 决策: {action}")

            if action == "respond":
                return await _generate_response(state, llm)
            elif action == "replan":
                if len(new_steps) > len(plan):
                    new_steps = new_steps[:len(plan)]
                if len(past_steps) >= 5:
                    return await _generate_response(state, llm)
                if new_steps:
                    return {"plan": new_steps}
                return {}
            else:
                return {}
        except Exception as e:
            logger.error(f"重新规划失败: {e}, 继续执行剩余计划")
            return {}
    else:
        logger.info("计划已执行完毕，生成最终响应")
        return await _generate_response(state, llm)


async def _generate_response(state: PlanExecuteState, llm) -> Dict[str, Any]:
    logger.info("生成最终响应...")
    input_text = state.get("input", "")
    past_steps = state.get("past_steps", [])

    execution_history = "\n\n".join([
        f"### 步骤: {step}\n**结果:**\n{result}"
        for step, result in past_steps
    ])

    response_gen = response_prompt | llm.with_structured_output(Response)
    try:
        messages = [
            ("user", f"原始任务: {input_text}"),
            ("user", f"执行历史:\n{execution_history}"),
            ("user", "请基于以上信息生成全面的最终响应")
        ]
        response_obj = await response_gen.ainvoke({"messages": messages})

        if isinstance(response_obj, Response):
            final_response = response_obj.response
        else:
            final_response = response_obj.get("response", "")

        logger.info(f"最终响应生成完成，长度: {len(final_response)}")
        return {"response": final_response}
    except Exception as e:
        logger.error(f"生成响应失败: {e}")
        fallback = f"# 任务执行结果\n\n## 原始任务\n{input_text}\n\n## 执行的步骤\n{_format_simple_steps(past_steps)}\n\n## 说明\n系统异常，无法生成完整响应。"
        return {"response": fallback}


def _format_simple_steps(past_steps: list) -> str:
    if not past_steps:
        return "无"
    formatted = []
    for i, (step, result) in enumerate(past_steps, 1):
        result_preview = result[:200] + "..." if len(result) > 200 else result
        formatted.append(f"{i}. **{step}**\n   {result_preview}\n")
    return "\n".join(formatted)
