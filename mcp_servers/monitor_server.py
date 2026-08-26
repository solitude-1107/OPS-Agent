"""智能运维监控 MCP Server"""

import logging
import functools
import json
import random
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Monitor_MCP_Server")
mcp = FastMCP("Monitor")


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
def query_cpu_metrics(service_name: str, start_time: Optional[str] = None, end_time: Optional[str] = None, interval: str = "1m") -> Dict[str, Any]:
    start_dt = parse_time_or_default(start_time, default_offset_hours=-1)
    end_dt = parse_time_or_default(end_time, default_offset_hours=0)
    interval_minutes = int(interval[:-1]) if interval.endswith('m') else int(interval[:-1]) * 60 if interval.endswith('h') else 1
    data_points = []
    current_time = start_dt
    time_index = 0
    while current_time <= end_dt:
        cpu_value = 10.0 + (time_index * 8.5) if time_index >= 3 else 10.0 + (time_index * 0.5)
        cpu_value = round(min(max(cpu_value + random.uniform(-2, 2), 0), 100), 1)
        data_points.append({"timestamp": current_time.strftime("%H:%M"), "value": cpu_value})
        current_time += timedelta(minutes=interval_minutes)
        time_index += 1
    if data_points:
        values = [d["value"] for d in data_points]
        return {"service_name": service_name, "metric_name": "cpu_usage_percent", "data_points": data_points,
                "statistics": {"avg": round(sum(values)/len(values), 2), "max": max(values), "min": min(values)}}
    return {"service_name": service_name, "data_points": []}


@mcp.tool()
@log_tool_call
def query_memory_metrics(service_name: str, start_time: Optional[str] = None, end_time: Optional[str] = None, interval: str = "1m") -> Dict[str, Any]:
    start_dt = parse_time_or_default(start_time, default_offset_hours=-1)
    end_dt = parse_time_or_default(end_time, default_offset_hours=0)
    interval_minutes = int(interval[:-1]) if interval.endswith('m') else int(interval[:-1]) * 60 if interval.endswith('h') else 1
    data_points = []
    current_time = start_dt
    time_index = 0
    total_gb = 8.0
    while current_time <= end_dt:
        memory_value = 30.0 + (time_index * 5.5) if time_index >= 3 else 30.0 + (time_index * 1.0)
        memory_value = round(min(max(memory_value + random.uniform(-1, 1), 0), 100), 1)
        data_points.append({"timestamp": current_time.strftime("%H:%M"), "value": memory_value, "used_gb": round((memory_value/100.0)*total_gb, 2), "total_gb": total_gb})
        current_time += timedelta(minutes=interval_minutes)
        time_index += 1
    if data_points:
        values = [d["value"] for d in data_points]
        return {"service_name": service_name, "metric_name": "memory_usage_percent", "data_points": data_points,
                "statistics": {"avg": round(sum(values)/len(values), 2), "max": max(values), "min": min(values)}}
    return {"service_name": service_name, "data_points": []}


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8004, path="/mcp")