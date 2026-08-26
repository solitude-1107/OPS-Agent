"""混合检索服务 - 向量检索 + BM25 + RRF 融合 + Rerank 精排"""

from typing import Dict, List, Tuple
from langchain_core.documents import Document
from loguru import logger
from app.config import config
from app.services.bm25_service import bm25_service
from app.services.reranker_service import reranker_service
from app.services.vector_store_manager import vector_store_manager


class HybridSearchService:
    def __init__(self):
        self._index_built = False
        logger.info("混合检索服务初始化完成")

    def _ensure_bm25_index(self):
        if self._index_built:
            return
        try:
            vector_store = vector_store_manager.get_vector_store()
            all_docs = vector_store.similarity_search("", k=1000)
            if all_docs:
                bm25_service.build_index(all_docs)
                self._index_built = True
                logger.info(f"BM25 索引构建完成, 文档数: {len(all_docs)}")
            else:
                logger.warning("未能从 Milvus 加载文档，BM25 索引为空")
        except Exception as e:
            logger.error(f"构建 BM25 索引失败: {e}")

    def search(self, query: str, top_k: int | None = None, use_rerank: bool | None = None) -> List[Document]:
        recall_k = config.rag_recall_k
        if use_rerank is None:
            use_rerank = config.rerank_enabled
        vector_docs = self._vector_recall(query, recall_k)
        bm25_results = self._bm25_recall(query, recall_k)
        fused_docs = self._rrf_fusion(vector_docs, bm25_results, recall_k)
        if not fused_docs:
            return []
        if use_rerank and len(fused_docs) > 1:
            ranked = reranker_service.rerank(query, fused_docs)
            final = reranker_service.dynamic_top_n(ranked)
            return [r.document for r in final]
        else:
            k = top_k or config.rag_top_k
            return fused_docs[:k]

    def _vector_recall(self, query: str, top_n: int) -> List[Document]:
        try:
            vector_store = vector_store_manager.get_vector_store()
            docs = vector_store.similarity_search(query, k=top_n)
            return docs
        except Exception as e:
            logger.error(f"向量召回失败: {e}")
            return []

    def _bm25_recall(self, query: str, top_n: int) -> List[Tuple[int, float]]:
        self._ensure_bm25_index()
        return bm25_service.search(query, top_n=top_n)

    def _rrf_fusion(self, vector_docs: List[Document], bm25_results: List[Tuple[int, float]], top_n: int) -> List[Document]:
        k = 60
        doc_map: Dict[str, Document] = {}
        for doc in vector_docs:
            doc_id = self._doc_id(doc)
            doc_map[doc_id] = doc
        for idx, _ in bm25_results:
            doc = bm25_service.documents[idx] if idx < len(bm25_service.documents) else None
            if doc:
                doc_id = self._doc_id(doc)
                doc_map[doc_id] = doc
        rrf_scores: Dict[str, float] = {}
        for rank, doc in enumerate(vector_docs, 1):
            doc_id = self._doc_id(doc)
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank)
        for rank, (idx, _) in enumerate(bm25_results, 1):
            if idx < len(bm25_service.documents):
                doc = bm25_service.documents[idx]
                doc_id = self._doc_id(doc)
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank)
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        fused = [doc_map[did] for did in sorted_ids[:top_n] if did in doc_map]
        logger.info(f"RRF 融合完成: 向量 {len(vector_docs)} 条 + BM25 {len(bm25_results)} 条 -> 融合后 {len(fused)} 条")
        return fused

    @staticmethod
    def _doc_id(doc: Document) -> str:
        return doc.page_content[:200]


hybrid_search_service = HybridSearchService()