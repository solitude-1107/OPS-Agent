"""BM25 检索服务 - 基于关键词的文档检索"""

from typing import List, Tuple
import jieba
from langchain_core.documents import Document
from loguru import logger
from rank_bm25 import BM25Okapi


class BM25Service:
    def __init__(self):
        self.corpus: List[str] = []
        self.tokenized_corpus: List[List[str]] = []
        self.documents: List[Document] = []
        self.bm25: BM25Okapi | None = None
        logger.info("BM25 检索服务初始化完成")

    def build_index(self, documents: List[Document]):
        if not documents:
            logger.warning("文档列表为空，跳过索引构建")
            return
        self.documents = documents
        self.corpus = [doc.page_content for doc in documents]
        self.tokenized_corpus = [list(jieba.cut(text)) for text in self.corpus]
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        logger.info(f"BM25 索引构建完成, 文档数: {len(documents)}")

    def search(self, query: str, top_n: int = 15) -> List[Tuple[int, float]]:
        if self.bm25 is None or not self.documents:
            logger.warning("BM25 索引未构建或为空")
            return []
        tokenized_query = list(jieba.cut(query))
        scores = self.bm25.get_scores(tokenized_query)
        scored_indices = [(i, scores[i]) for i in range(len(scores)) if scores[i] > 0]
        scored_indices.sort(key=lambda x: x[1], reverse=True)
        top_results = scored_indices[:top_n]
        logger.info(f"BM25 检索完成: query='{query[:50]}...', 有分数文档 {len(scored_indices)} 条, 返回 {len(top_results)} 条")
        return top_results

    def get_documents_by_indices(self, indices: List[int]) -> List[Document]:
        return [self.documents[i] for i in indices if i < len(self.documents)]


bm25_service = BM25Service()
