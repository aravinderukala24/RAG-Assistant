import os
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Generator
from ..config import settings
from ..models.schemas import AnalyzeResponse, ChatResponse, CodeSource, TraceStep
from .github_service import GitHubService
from .chunking_service import ChunkingService, CodeChunk
from .embedding_service import EmbeddingService
from .vector_service import VectorService
from .llm_service import LLMService


class RAGService:
    def __init__(self):
        self.github_service = GitHubService()
        self.chunking_service = ChunkingService()
        self.embedding_service = EmbeddingService()
        self.vector_service = VectorService()
        self.llm_service = LLMService()

    def analyze_repository_stream(self, repo_url: str) -> Generator[Dict[str, Any], None, None]:
        """
        Orchestrates full ingestion with real-time progress streaming.
        Yields JSON-serializable dicts describing the current stage and progress.
        """

        # ── Stage 1: Cloning ──
        yield {
            "stage": "cloning",
            "status": "Cloning repository...",
            "progress": 5,
        }
        repo_dir, repo_key, repo_name = self.github_service.clone_or_update_repo(repo_url)
        yield {
            "stage": "cloning",
            "status": f"Cloned {repo_name}",
            "progress": 15,
        }

        # ── Stage 2: Scanning ──
        yield {
            "stage": "scanning",
            "status": "Scanning for source files...",
            "progress": 18,
        }
        source_files = self.github_service.scan_source_files(repo_dir)
        if not source_files:
            yield {
                "stage": "error",
                "status": f"No supported source files found in {repo_name}.",
                "progress": 0,
            }
            return

        languages = sorted(list(set(f["language"] for f in source_files)))
        yield {
            "stage": "scanning",
            "status": f"Found {len(source_files)} source files",
            "detail": f"Languages: {', '.join(languages)}",
            "progress": 25,
        }

        # ── Stage 3: Parsing & Chunking ──
        yield {
            "stage": "chunking",
            "status": "Parsing and chunking source code...",
            "current": 0,
            "total": len(source_files),
            "progress": 28,
        }

        all_chunks: List[CodeChunk] = []
        for i, file_info in enumerate(source_files):
            try:
                content = file_info["full_path"].read_text(encoding="utf-8", errors="replace")
                chunks = self.chunking_service.chunk_file(
                    code=content,
                    file_path=file_info["relative_path"],
                    language=file_info["language"],
                    repo_key=repo_key,
                    repo_name=repo_name
                )
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"Skipping file {file_info['relative_path']}: {e}")
                continue

            # Yield progress every 5 files or on the last file
            if (i + 1) % 5 == 0 or i == len(source_files) - 1:
                chunk_progress = 28 + int(((i + 1) / len(source_files)) * 12)
                yield {
                    "stage": "chunking",
                    "status": f"Parsing files ({i + 1}/{len(source_files)})",
                    "detail": f"{len(all_chunks)} chunks created",
                    "current": i + 1,
                    "total": len(source_files),
                    "progress": min(chunk_progress, 40),
                }

        if not all_chunks:
            yield {
                "stage": "error",
                "status": f"Could not extract any code chunks from {repo_name}.",
                "progress": 0,
            }
            return

        yield {
            "stage": "chunking",
            "status": f"Created {len(all_chunks)} code chunks from {len(source_files)} files",
            "current": len(source_files),
            "total": len(source_files),
            "progress": 40,
        }

        # ── Stage 4: Embedding ──
        yield {
            "stage": "embedding",
            "status": "Generating embeddings...",
            "current": 0,
            "total": len(all_chunks),
            "progress": 42,
        }

        texts_to_embed = [c.text_for_embedding for c in all_chunks]
        embeddings: List[List[float]] = []
        total_chunks = len(texts_to_embed)

        for idx, embedding in self.embedding_service.generate_embeddings_stream(texts_to_embed):
            embeddings.append(embedding)
            done_count = idx + 1

            # Yield progress every 3 embeddings or on the last one
            if done_count % 3 == 0 or done_count == total_chunks:
                embed_progress = 42 + int((done_count / total_chunks) * 48)
                yield {
                    "stage": "embedding",
                    "status": f"Generating embeddings ({done_count}/{total_chunks})",
                    "current": done_count,
                    "total": total_chunks,
                    "progress": min(embed_progress, 90),
                }

        # ── Stage 5: Indexing ──
        yield {
            "stage": "indexing",
            "status": "Building search index...",
            "progress": 92,
        }
        self.vector_service.index_chunks(repo_key, all_chunks, embeddings)
        yield {
            "stage": "indexing",
            "status": "Search index built",
            "progress": 98,
        }

        # ── Stage 6: Complete ──
        yield {
            "stage": "complete",
            "status": "Repository Ready",
            "progress": 100,
            "result": {
                "repository": repo_key,
                "repo_name": repo_name,
                "status": "indexed",
                "files_scanned": len(source_files),
                "chunks_indexed": len(all_chunks),
                "languages": languages,
                "message": f"Successfully indexed {len(source_files)} files into {len(all_chunks)} semantic chunks.",
            }
        }

    def analyze_repository(self, repo_url: str) -> AnalyzeResponse:
        """
        Non-streaming wrapper. Runs the full pipeline and returns the final result.
        Kept for backward compatibility.
        """
        result = None
        for event in self.analyze_repository_stream(repo_url):
            if event.get("stage") == "error":
                raise ValueError(event.get("status", "Unknown error"))
            if event.get("stage") == "complete":
                result = event.get("result")
        if result is None:
            raise RuntimeError("Ingestion pipeline did not produce a result.")
        return AnalyzeResponse(**result)

    def answer_question(self, repo_identifier: str, question: str, top_k: int = 6) -> ChatResponse:
        """
        Orchestrates question answering: query embed -> retrieve -> LLM grounding -> citation assembly.
        """
        # Normalize repository identifier
        if "github.com" in repo_identifier or "/" in repo_identifier:
            _, repo_key, repo_name = self.github_service.parse_repo_url(repo_identifier)
        else:
            repo_key = repo_identifier
            repo_name = repo_identifier.replace("__", "/")

        # Check if indexed
        if not self.vector_service.is_repo_indexed(repo_key):
            raise ValueError(f"Repository '{repo_name}' is not indexed yet. Please analyze the repository first.")

        # 1. Generate query embedding
        query_embedding = self.embedding_service.generate_query_embedding(question)

        # 2. Retrieve top-K similar chunks from ChromaDB
        retrieved_chunks = self.vector_service.query_similar_chunks(
            repo_key=repo_key,
            query_embedding=query_embedding,
            top_k=top_k
        )

        if not retrieved_chunks:
            return ChatResponse(
                question=question,
                repository=repo_name,
                answer="No relevant code was found in the repository index for this question.",
                sources=[],
                trace_flow=[]
            )

        # 3. Format sources
        sources: List[CodeSource] = []
        for chunk in retrieved_chunks:
            source = CodeSource(
                file_path=chunk["file_path"],
                function_name=chunk.get("function_name"),
                class_name=chunk.get("class_name"),
                start_line=chunk.get("start_line", 1),
                end_line=chunk.get("end_line", 1),
                language=chunk.get("language", "text"),
                snippet=chunk.get("source_code", ""),
                similarity_score=chunk.get("similarity")
            )
            sources.append(source)

        # 4. Generate grounded LLM response
        answer_text, trace_flow = self.llm_service.generate_grounded_answer(
            question=question,
            retrieved_chunks=retrieved_chunks,
            repo_name=repo_name
        )

        return ChatResponse(
            question=question,
            repository=repo_name,
            answer=answer_text,
            sources=sources,
            trace_flow=trace_flow
        )
