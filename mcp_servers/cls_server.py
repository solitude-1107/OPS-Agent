"""腾讯云 CLS MCP Server"""

import logging
import functools
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CLS_MCP_Server")
mcp = FastMCP("CLS")


def log_tool_call(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        method_name = func.__name__
        logger.info(f"调用方法: {method_name}")
        if kwargs:
            try:
                params_str = json.dumps(kwargs, ensure_ascii=False, indent=2)
            except (TypeError, ValueError):
                params_str = str(kwargs)
            logger.info(f"参数信息:\n{params_str}")
        try:
            result = func(*args, **kwargs)
            logger.info(f"返回状态: SUCCESS")
            return result
        except Exception as e:
            logger.error(f"返回状态: ERROR - {str(e)}")
            raise
    return wrapper


def parse_time_or_default(time_str: Optional[str], default_offset_hours: int = 0) -> datetime:
    if time_str:
        try:
            return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return datetime.now() + timedelta(hours=default_offset_hours)


@mcp.tool()
@log_tool_call
def get_current_timestamp() -> int:
    """获取当前毫秒时间戳"""
    return int(datetime.now().timestamp() * 1000)


@mcp.tool()
@log_tool_call
def get_topic_info_by_name(topic_name: str, region_code: Optional[str] = None) -> Dict[str, Any]:
    mock_topics = [
        {"topic_id": "topic-001", "topic_name": "数据同步服务日志", "service_name": "data-sync-service",
         "region_code": "ap-beijing", "create_time": "2024-01-01 10:00:00", "log_count": 0}
    ]
    for topic in mock_topics:
        if topic["topic_name"] == topic_name:
            if region_code is None or topic["region_code"] == region_code:
                return topic
    return {"topic_id": None, "topic_name": topic_name, "error": f"未找到主题: {topic_name}"}


@mcp.tool()
@log_tool_call
def search_log(topic_id: str, start_time: int, end_time: int, query: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    if topic_id == "topic-001":
        logs = []
        current_time_ms = start_time
        max_logs = min(limit, int((end_time - start_time) / (60 * 1000)) + 1)
        while current_time_ms <= end_time and len(logs) < max_logs:
            log_time = datetime.fromtimestamp(current_time_ms / 1000)
            logs.append({"timestamp": log_time.strftime("%Y-%m-%d %H:%M:%S"), "level": "INFO", "message": "正在同步元数据……"})
            current_time_ms += 60 * 1000
        return {"topic_id": topic_id, "total": len(logs), "logs": logs, "took_ms": 50}
    return {"topic_id": topic_id, "total": 0, "logs": [], "error": f"主题不存在: {topic_id}"}


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8003, path="/mcp")