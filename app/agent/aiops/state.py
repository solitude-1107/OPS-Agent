"""
通用 Plan-Execute-Replan 状态定义
"""

from typing import List, TypedDict, Annotated
import operator


class PlanExecuteState(TypedDict):
    input: str
    plan: List[str]
    past_steps: Annotated[List[tuple], operator.add]
    response: str
