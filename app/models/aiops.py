"""
AIOps 请求和响应模型
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AIOpsRequest(BaseModel):
    """AIOps 诊断请求"""
    session_id: Optional[str] = Field(default="default", description="会话ID，用于追踪诊断历史")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session-123"
            }
        }


class AlertInfo(BaseModel):
    alertname: str
    severity: str
    instance: str
    duration: str
    description: Optional[str] = None


class DiagnosisResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Dict[str, Any]