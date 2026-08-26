"""向量检索服务模块"""

from typing import Any, Dict, List
from loguru import logger
from pymilvus import Collection
from app.core.milvus_client import milvus_manager
from app.services.vector_embedding_service import vector_embedding_service


class SearchResult:
    def __init__(self, id: str, content: str, score: float, metadata: Dict[str, Any]):
        self.id = id
        self.content = content
        self.score = score
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "content": self.content, "score": self.score, "metadata": self.metadata}


class VectorSearchService:
    def __init__(self):
        logger.info("向量检索服务初始化完成")

    def search_similar_documents(self, query: str, top_k: int = 3) -> List[SearchResult]:
        try:
            logger.info(f"开始搜索相似文档, 查询: {query}, topK: {top_k}")
            query_vector = vector_embedding_service.embed_query(query)
            collection: Collection = milvus_manager.get_collection()
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            results = collection.search(data=[query_vector], anns_field="vector", param=search_params, limit=top_k, output_fields=["id", "content", "metadata"])
            search_results = []
            for hits in results:
                for hit in hits:
                    result = SearchResult(id=hit.entity.get("id"), content=hit.entity.get("content"), score=hit.distance, metadata=hit.entity.get("metadata", {}))
                    search_results.append(result)
            logger.info(f"搜索完成, 找到 {len(search_results)} 个相似文档")
            return search_results
        except Exception as e:
            logger.error(f"搜索相似文档失败: {e}")
            raise RuntimeError(f"搜索失败: {e}") from e


vector_search_service = VectorSearchService()
