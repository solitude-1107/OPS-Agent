"""文件上传接口模块"""

from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from app.services.vector_index_service import vector_index_service
from app.services.vector_store_manager import vector_store_manager
from app.api.deps import verify_api_key
from loguru import logger

router = APIRouter()
UPLOAD_DIR = Path("./uploads")
ALLOWED_EXTENSIONS = ["txt", "md"]
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), _=Depends(verify_api_key)):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        safe_filename = _sanitize_filename(file.filename)
        file_extension = _get_file_extension(safe_filename)
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式，仅支持: {', '.join(ALLOWED_EXTENSIONS)}")
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        file_path = UPLOAD_DIR / safe_filename
        if file_path.exists():
            logger.info(f"文件已存在，将覆盖: {file_path}")
            file_path.unlink()
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"文件大小超过限制（最大 {MAX_FILE_SIZE} 字节）")
        file_hash = vector_store_manager.compute_file_hash(content)
        if vector_store_manager.is_file_indexed(safe_filename, file_hash):
            return JSONResponse(status_code=200, content={"code": 200, "message": "success", "data": {"filename": safe_filename, "file_path": str(file_path), "size": len(content), "skipped": True, "reason": "文件内容未变化，跳过索引"}})
        file_path.write_bytes(content)
        logger.info(f"文件上传成功: {file_path}")
        try:
            logger.info(f"开始为上传文件创建向量索引: {file_path}")
            vector_index_service.index_single_file(str(file_path))
            vector_store_manager.record_file_hash(safe_filename, file_hash)
            logger.info(f"向量索引创建成功: {file_path}")
        except Exception as e:
            logger.error(f"向量索引创建失败: {file_path}, 错误: {e}")
        return JSONResponse(status_code=200, content={"code": 200, "message": "success", "data": {"filename": safe_filename, "file_path": str(file_path), "size": len(content)}})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {e}")


@router.post("/index_directory")
async def index_directory(directory_path: str = None, _=Depends(verify_api_key)):
    try:
        logger.info(f"开始索引目录: {directory_path or 'uploads'}")
        result = vector_index_service.index_directory(directory_path)
        return JSONResponse(status_code=200, content={"code": 200, "message": "success" if result.success else "partial_success", "data": result.to_dict()})
    except Exception as e:
        logger.error(f"索引目录失败: {e}")
        raise HTTPException(status_code=500, detail=f"索引目录失败: {e}")


def _get_file_extension(filename: str) -> str:
    parts = filename.rsplit(".", 1)
    if len(parts) == 2:
        return parts[1].lower()
    return ""


def _sanitize_filename(filename: str) -> str:
    sanitized = filename.replace(" ", "_")
    for char in ['\\\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        sanitized = sanitized.replace(char, "_")
    return sanitized