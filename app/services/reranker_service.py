"""Reranker 服务 - 基于 DashScope gte-rerank 模型对文档重排序"""

from dataclasses import dataclass
from typing import List
from dashscope import TextReRank
from langchain_core.documents import Document
from loguru import logger
from app.config import config


@dataclass
class RerankResult:
    document: Document
    score: float
    original_index: int


class RerankerService:
    def __init__(self):
        self.model = config.rerank_model
        self.api_key = config.dashscope_api_key
        logger.info(f"Reranker 服务初始化完成, model={self.model}")

    def rerank(self, query: str, documents: List[Document], top_n: int | None = None) -> List[RerankResult]:
        if not documents:
            return []
        if len(documents) == 1:
            return [RerankResult(document=documents[0], score=1.0, original_index=0)]
        try:
            doc_texts = [doc.page_content for doc in documents]
            response = TextReRank.call(model=self.model, query=query, documents=doc_texts, top_n=top_n, return_documents=False, api_key=self.api_key)
            results = []
            if response.output and response.output.get("results"):
                for item in response.output["results"]:
                    idx = item.get("index", 0)
                    score = item.get("relevance_score", 0.0)
                    results.append(RerankResult(document=documents[idx], score=score, original_index=idx))
            logger.info(f"Rerank 完成: query='{query[:50]}...', 输入 {len(documents)} 条, 输出 {len(results)} 条")
            return results
        except Exception as e:
            logger.error(f"Rerank 调用失败: {e}, 回退到原始顺序")
            return [RerankResult(document=doc, score=0.0, original_index=i) for i, doc in enumerate(documents)]

    def dynamic_top_n(self, ranked_results: List[RerankResult]) -> List[RerankResult]:
        if not ranked_results:
            return []
        min_score = config.rag_rerank_min_score
        max_docs = config.rag_rerank_max_docs
        min_docs = config.rag_rerank_min_docs
        filtered = [r for r in ranked_results if r.score >= min_score]
        filtered = filtered[:max_docs]
        if len(filtered) < min_docs:
            filtered = ranked_results[:min_docs]
        logger.info(f"动态 Top-N: 输入 {len(ranked_results)} 条, 过滤后 {len(filtered)} 条")
        return filtered


reranker_service = RerankerService()
