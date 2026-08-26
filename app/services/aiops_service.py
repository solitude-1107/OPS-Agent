"""
通用 Plan-Execute-Replan 服务
"""

from typing import AsyncGenerator, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from loguru import logger
from app.agent.aiops import PlanExecuteState, planner, executor, replanner


NODE_PLANNER = "planner"
NODE_EXECUTOR = "executor"
NODE_REPLANNER = "replanner"


class AIOpsService:
    def __init__(self):
        self.checkpointer = MemorySaver()
        self.graph = self._build_graph()
        logger.info("Plan-Execute-Replan Service 初始化完成")

    def _build_graph(self):
        workflow = StateGraph(PlanExecuteState)
        workflow.add_node(NODE_PLANNER, planner)
        workflow.add_node(NODE_EXECUTOR, executor)
        workflow.add_node(NODE_REPLANNER, replanner)
        workflow.set_entry_point(NODE_PLANNER)
        workflow.add_edge(NODE_PLANNER, NODE_EXECUTOR)
        workflow.add_edge(NODE_EXECUTOR, NODE_REPLANNER)

        def should_continue(state: PlanExecuteState) -> str:
            if state.get("response"):
                return END
            plan = state.get("plan", [])
            if plan:
                return NODE_EXECUTOR
            return END

        workflow.add_conditional_edges(NODE_REPLANNER, should_continue, {NODE_EXECUTOR: NODE_EXECUTOR, END: END})
        return workflow.compile(checkpointer=self.checkpointer)

    async def execute(self, user_input: str, session_id: str = "default") -> AsyncGenerator[Dict[str, Any], None]:
        try:
            initial_state: PlanExecuteState = {"input": user_input, "plan": [], "past_steps": [], "response": ""}
            config_dict = {"configurable": {"thread_id": session_id}}
            async for event in self.graph.astream(input=initial_state, config=config_dict, stream_mode="updates"):
                for node_name, node_output in event.items():
                    if node_name == NODE_PLANNER:
                        yield self._format_planner_event(node_output)
                    elif node_name == NODE_EXECUTOR:
                        yield self._format_executor_event(node_output)
                    elif node_name == NODE_REPLANNER:
                        yield self._format_replanner_event(node_output)
            final_state = self.graph.get_state(config_dict)
            final_response = final_state.values.get("response", "") if final_state and final_state.values else ""
            yield {"type": "complete", "stage": "complete", "message": "任务执行完成", "response": final_response}
        except Exception as e:
            logger.error(f"[会话 {session_id}] 任务执行失败: {e}")
            yield {"type": "error", "stage": "error", "message": f"任务执行出错: {str(e)}"}

    async def diagnose(self, session_id: str = "default") -> AsyncGenerator[Dict[str, Any], None]:
        from textwrap import dedent
        aiops_task = dedent("""诊断当前系统是否存在告警，如果存在告警请详细分析告警原因并生成诊断报告""")
        async for event in self.execute(aiops_task, session_id):
            if event.get("type") == "complete":
                yield {"type": "complete", "stage": "diagnosis_complete", "message": "诊断流程完成", "diagnosis": {"status": "completed", "report": event.get("response", "")}}
            else:
                yield event

    def _format_planner_event(self, state: Dict | None) -> Dict:
        if not state:
            return {"type": "status", "stage": "planner", "message": "规划节点执行中"}
        plan = state.get("plan", [])
        return {"type": "plan", "stage": "plan_created", "message": f"执行计划已制定，共 {len(plan)} 个步骤", "plan": plan}

    def _format_executor_event(self, state: Dict | None) -> Dict:
        if not state:
            return {"type": "status", "stage": "executor", "message": "执行节点运行中"}
        plan = state.get("plan", [])
        past_steps = state.get("past_steps", [])
        if past_steps:
            last_step, _ = past_steps[-1]
            return {"type": "step_complete", "stage": "step_executed", "message": f"步骤执行完成 ({len(past_steps)}/{len(past_steps) + len(plan)})", "current_step": last_step, "remaining_steps": len(plan)}
        return {"type": "status", "stage": "executor", "message": "开始执行步骤"}

    def _format_replanner_event(self, state: Dict | None) -> Dict:
        if not state:
            return {"type": "status", "stage": "replanner", "message": "评估节点运行中"}
        response = state.get("response", "")
        plan = state.get("plan", [])
        if response:
            return {"type": "report", "stage": "final_report", "message": "最终报告已生成", "report": response}
        return {"type": "status", "stage": "replanner", "message": f"评估完成，{'继续执行剩余步骤' if plan else '准备生成最终响应'}", "remaining_steps": len(plan)}


aiops_service = AIOpsService()