"""Prometheus 告警查询工具"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
import httpx
from langchain_core.tools import tool
from loguru import logger
from app.config import config

ALERTS_API_PATH = "/api/v1/alerts"
COMMON_LABEL_KEYS = ("alertname", "severity", "instance", "job", "namespace", "pod")


def _parse_active_at(active_at_str: str) -> datetime | None:
    if not active_at_str:
        return None
    try:
        s = active_at_str.replace("Z", "+00:00", 1)
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _labels_identity(labels: dict[str, Any]) -> str:
    return json.dumps(labels, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def calculate_duration(active_at_str: str) -> str:
    active_at = _parse_active_at(active_at_str)
    if active_at is None:
        return "unknown"
    now = datetime.now(timezone.utc)
    delta = now - active_at
    total_seconds = max(0, int(delta.total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}h{minutes}m{seconds}s"
    if minutes > 0:
        return f"{minutes}m{seconds}s"
    return f"{seconds}s"


def query_prometheus_alerts_api() -> tuple[dict[str, Any], str | None]:
    base_url = config.prometheus_base_url.rstrip("/")
    api_url = f"{base_url}{ALERTS_API_PATH}"
    logger.info("Querying Prometheus alerts: {}", api_url)
    try:
        with httpx.Client(timeout=config.prometheus_request_timeout) as client:
            resp = client.get(api_url)
            resp.raise_for_status()
            body = resp.json()
    except httpx.HTTPError as e:
        return {}, f"failed to query Prometheus alerts: {e}"
    except json.JSONDecodeError as e:
        return {}, f"failed to parse response: {e}"
    return body, None


def _pick_common_labels(labels: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in COMMON_LABEL_KEYS:
        if k == "alertname":
            continue
        v = labels.get(k)
        if v is not None and v != "":
            out[k] = v
    return out


def _simplify_alerts(result: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    data = result.get("data") or {}
    alerts = data.get("alerts") or []
    if not isinstance(alerts, list):
        return [], {}
    simplified: list[dict[str, Any]] = []
    seen_identity: set[str] = set()
    state_counts: dict[str, int] = {}
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        labels = alert.get("labels") or {}
        annotations = alert.get("annotations") or {}
        if not isinstance(labels, dict):
            labels = {}
        if not isinstance(annotations, dict):
            annotations = {}
        identity = _labels_identity(labels)
        if identity in seen_identity:
            continue
        seen_identity.add(identity)
        state = str(alert.get("state", "") or "")
        state_counts[state] = state_counts.get(state, 0) + 1
        active_at = str(alert.get("activeAt", "") or "")
        alert_name = str(labels.get("alertname", "") or "")
        simplified.append({
            "alert_name": alert_name,
            "labels": labels,
            "common_labels": _pick_common_labels(labels),
            "description": str(annotations.get("description", "") or ""),
            "summary": str(annotations.get("summary", "") or ""),
            "state": state,
            "active_at": active_at,
            "duration": calculate_duration(active_at),
        })

    def sort_key(item: dict[str, Any]) -> tuple[int, float]:
        dt = _parse_active_at(str(item.get("active_at", "")))
        if dt is None:
            return (1, 0.0)
        return (0, -dt.timestamp())

    simplified.sort(key=sort_key)
    return simplified, state_counts


@tool
def query_prometheus_alerts() -> str:
    """查询 Prometheus 服务端当前活动告警"""
    result, err = query_prometheus_alerts_api()
    if err:
        out = {"success": False, "error": err, "message": "Failed to query Prometheus alerts"}
        return json.dumps(out, ensure_ascii=False, indent=2)

    if result.get("status") != "success":
        err_msg = result.get("error") or result.get("errorType") or "Prometheus returned non-success status"
        out = {"success": False, "error": str(err_msg), "message": "Failed to query Prometheus alerts"}
        return json.dumps(out, ensure_ascii=False, indent=2)

    simplified, state_counts = _simplify_alerts(result)
    out = {
        "success": True,
        "alerts": simplified,
        "state_counts": state_counts,
        "total": len(simplified),
        "message": f"已获取 {len(simplified)} 条告警，状态分布: {state_counts}",
    }
    logger.info("Prometheus alerts query completed: {} alerts, states={}", len(simplified), state_counts)
    return json.dumps(out, ensure_ascii=False, indent=2)
