"""向量存储管理器 - 封装 Milvus VectorStore 操作"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional
from langchain_core.documents import Document
from langchain_milvus import Milvus
from loguru import logger
from app.config import config
from app.core.milvus_client import milvus_manager
from app.services.vector_embedding_service import vector_embedding_service

COLLECTION_NAME = "biz"
FILE_HASH_DB_PATH = Path("data/file_hashes.json")


class VectorStoreManager:
    def __init__(self):
        self.vector_store = None
        self.collection_name = COLLECTION_NAME
        self._file_hashes: Dict[str, str] = {}
        self._load_file_hashes()
        self._initialize_vector_store()

    def _load_file_hashes(self):
        try:
            if FILE_HASH_DB_PATH.exists():
                with open(FILE_HASH_DB_PATH, "r", encoding="utf-8") as f:
                    self._file_hashes = json.load(f)
                logger.info(f"已加载 {len(self._file_hashes)} 个文件哈希记录")
        except Exception as e:
            logger.warning(f"加载文件哈希记录失败: {e}")
            self._file_hashes = {}

    def _save_file_hashes(self):
        try:
            FILE_HASH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(FILE_HASH_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(self._file_hashes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存文件哈希记录失败: {e}")

    @staticmethod
    def compute_file_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def is_file_indexed(self, file_path: str, file_hash: str) -> bool:
        stored_hash = self._file_hashes.get(file_path)
        if stored_hash == file_hash:
            logger.info(f"文件未变化，跳过索引: {file_path}")
            return True
        return False

    def record_file_hash(self, file_path: str, file_hash: str):
        self._file_hashes[file_path] = file_hash
        self._save_file_hashes()

    def _initialize_vector_store(self):
        try:
            _ = milvus_manager.connect()
            connection_args = {"host": config.milvus_host, "port": config.milvus_port}
            self.vector_store = Milvus(embedding_function=vector_embedding_service, collection_name=self.collection_name, connection_args=connection_args, auto_id=False, drop_old=False, text_field="content", vector_field="vector", primary_field="id", metadata_field="metadata")
            logger.info(f"VectorStore 初始化成功: {config.milvus_host}:{config.milvus_port}, collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"VectorStore 初始化失败: {e}")
            raise

    def add_documents(self, documents: List[Document]) -> List[str]:
        try:
            import time
            import uuid
            start_time = time.time()
            ids = [str(uuid.uuid4()) for _ in documents]
            result_ids = self.vector_store.add_documents(documents, ids=ids)
            elapsed = time.time() - start_time
            logger.info(f"批量添加 {len(documents)} 个文档到 VectorStore 完成, 耗时: {elapsed:.2f}秒")
            return result_ids
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            raise

    def delete_by_source(self, file_path: str) -> int:
        try:
            collection = milvus_manager.get_collection()
            expr = f'metadata["_source"] == "{file_path}"'
            result = collection.delete(expr)
            deleted_count = result.delete_count if hasattr(result, "delete_count") else 0
            logger.info(f"删除文件旧数据: {file_path}, 删除数量: {deleted_count}")
            return deleted_count
        except Exception as e:
            logger.warning(f"删除旧数据失败 (可能是首次索引): {e}")
            return 0

    def get_vector_store(self) -> Milvus:
        return self.vector_store

    def similarity_search(self, query: str, k: int = 3) -> List[Document]:
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            return docs
        except Exception as e:
            logger.error(f"相似度搜索失败: {e}")
            return []


vector_store_manager = VectorStoreManager()