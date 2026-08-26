"""工具模块 - 供 Agent 调用的各种工具"""

from app.tools.knowledge_tool import retrieve_knowledge
from app.tools.query_metrics_alerts import query_prometheus_alerts
from app.tools.time_tool import get_current_time

DEFAULT_LOCAL_AGENT_TOOLS = (
    retrieve_knowledge,
    get_current_time,
    query_prometheus_alerts,
)

__all__ = [
    "DEFAULT_LOCAL_AGENT_TOOLS",
    "retrieve_knowledge",
    "get_current_time",
    "query_prometheus_alerts",
]
