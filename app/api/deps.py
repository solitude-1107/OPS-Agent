"""
API 依赖项 - 认证等公共依赖
"""

from fastapi import Header, HTTPException
from app.config import config


async def verify_api_key(authorization: str = Header(None)):
    if not config.api_key:
        return
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少认证信息，请在 Header 中提供 Authorization")
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    if token != config.api_key:
        raise HTTPException(status_code=401, detail="API Key 无效")