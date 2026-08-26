"""
AIOps 智能运维接口
"""

import json
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from loguru import logger

from app.models.aiops import AIOpsRequest
from app.services.aiops_service import aiops_service
from app.api.deps import verify_api_key

router = APIRouter()


@router.post("/aiops")
async def diagnose_stream(request: AIOpsRequest, _=Depends(verify_api_key)):
    session_id = request.session_id or "default"
    logger.info(f"[会话 {session_id}] 收到 AIOps 诊断请求（流式）")

    async def event_generator():
        try:
            async for event in aiops_service.diagnose(session_id=session_id):
                yield {"event": "message", "data": json.dumps(event, ensure_ascii=False)}
                if event.get("type") in ["complete", "error"]:
                    break
            logger.info(f"[会话 {session_id}] AIOps 诊断流式响应完成")
        except Exception as e:
            logger.error(f"[会话 {session_id}] AIOps 诊断流式响应异常: {e}", exc_info=True)
            yield {"event": "message", "data": json.dumps({"type": "error", "stage": "exception", "message": f"诊断异常: {str(e)}"}, ensure_ascii=False)}

    return EventSourceResponse(event_generator())