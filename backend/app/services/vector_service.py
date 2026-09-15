import re
import chromadb
from typing import List, Dict, Any, Optional
from ..config import settings
from .chunking_service import CodeChunk

class VectorService:
    def __init__(self):
        # Initialize persistent client
        self.client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))

    def _sanitize_collection_name(self, repo_key: str) -> str:
        """
        ChromaDB collections require: 3-63 chars, [a-zA-Z0-9._-], must start and end with alphanumeric.
        """
        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", repo_key)
        if len(clean) < 3:
            clean = f"repo_{clean}"
        clean = clean[:60]
        # Ensure starts and ends with alphanumeric
        clean = re.sub(r"^[^a-zA-Z0-9]+", "r_", clean)
        clean = re.sub(r"[^a-zA-Z0-9]+$", "_r", clean)
        return clean

    def get_or_create_collection(self, repo_key: str):
        collection_name = self._sanitize_collection_name(repo_key)
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def is_repo_indexed(self, repo_key: str) -> bool:
        """
        Checks if repository has indexed chunks in vector store.
        """
        try:
            collection_name = self._sanitize_collection_name(repo_key)
            # Try to get existing collection
            collection = self.client.get_collection(name=collection_name)
            return collection.count() > 0
        except Exception:
            return False

    def get_indexed_count(self, repo_key: str) -> int:
        try:
            collection = self.get_or_create_collection(repo_key)
            return collection.count()
        except Exception:
            return 0

    def index_chunks(self, repo_key: str, chunks: List[CodeChunk], embeddings: List[List[float]]):
        """
        Upserts code chunks and their embeddings into ChromaDB collection.
        """
        if not chunks or not embeddings or len(chunks) != len(embeddings):
            return

        collection = self.get_or_create_collection(repo_key)

        ids = [c.chunk_id for c in chunks]
        docs = [c.text_for_embedding for c in chunks]
        
        # ChromaDB metadata must have string, int, float, or bool values
        metadatas = []
        for c in chunks:
            m = c.metadata.copy()
            # Ensure proper types
            m["start_line"] = int(m.get("start_line", 1))
            m["end_line"] = int(m.get("end_line", 1))
            metadatas.append(m)

        # Batch upsert in chunks of 200 for ChromaDB efficiency
        batch_size = 200
        for i in range(0, len(ids), batch_size):
            collection.upsert(
                ids=ids[i : i + batch_size],
                embeddings=embeddings[i : i + batch_size],
                documents=docs[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size]
            )

    def query_similar_chunks(
        self,
        repo_key: str,
        query_embedding: List[float],
        top_k: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Performs cosine distance search and returns top-K matching code chunks with metadata.
        """
        collection = self.get_or_create_collection(repo_key)
        total_items = collection.count()
        if total_items == 0:
            return []

        actual_k = min(top_k, total_items)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_k,
            include=["metadatas", "documents", "distances"]
        )

        matched_chunks = []
        if results and "metadatas" in results and results["metadatas"]:
            metas = results["metadatas"][0]
            docs = results["documents"][0] if "documents" in results else []
            distances = results["distances"][0] if "distances" in results else []

            for idx, meta in enumerate(metas):
                dist = distances[idx] if idx < len(distances) else 1.0
                # Cosine similarity = 1 - cosine distance
                similarity = max(0.0, 1.0 - dist)
                
                chunk_data = {
                    "metadata": meta,
                    "document": docs[idx] if idx < len(docs) else "",
                    "similarity": round(similarity, 4),
                    "file_path": meta.get("file_path", ""),
                    "language": meta.get("language", ""),
                    "function_name": meta.get("function_name") or None,
                    "class_name": meta.get("class_name") or None,
                    "start_line": int(meta.get("start_line", 1)),
                    "end_line": int(meta.get("end_line", 1)),
                    "source_code": meta.get("source_code", docs[idx] if idx < len(docs) else "")
                }
                matched_chunks.append(chunk_data)

        return matched_chunks
