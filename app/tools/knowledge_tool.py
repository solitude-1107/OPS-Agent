"""知识检索工具 - 混合检索：向量 + BM25 + Rerank"""

from typing import List, Tuple
from langchain_core.documents import Document
from langchain_core.tools import tool
from loguru import logger
from app.services.hybrid_search_service import hybrid_search_service


@tool(response_format="content_and_artifact")
def retrieve_knowledge(query: str) -> Tuple[str, List[Document]]:
    """从知识库中检索相关信息来回答问题"""
    try:
        logger.info(f"知识检索工具被调用: query='{query}'")
        docs = hybrid_search_service.search(query)
        if not docs:
            logger.warning("未检索到相关文档")
            return "没有找到相关信息。", []
        context = format_docs(docs)
        logger.info(f"检索到 {len(docs)} 个相关文档")
        return context, docs
    except Exception as e:
        logger.error(f"知识检索工具调用失败: {e}")
        return f"检索知识时发生错误: {str(e)}", []


def format_docs(docs: List[Document]) -> str:
    formatted_parts = []
    for i, doc in enumerate(docs, 1):
        metadata = doc.metadata
        source = metadata.get("_file_name", "未知来源")
        headers = []
        for key in ["h1", "h2", "h3"]:
            if key in metadata and metadata[key]:
                headers.append(metadata[key])
        header_str = " > ".join(headers) if headers else ""
        formatted = f"【参考资料 {i}】"
        if header_str:
            formatted += f"\n标题: {header_str}"
        formatted += f"\n来源: {source}"
        formatted += f"\n内容:\n{doc.page_content}\n"
        formatted_parts.append(formatted)
    return "\n".join(formatted_parts)
