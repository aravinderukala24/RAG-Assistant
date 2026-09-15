import hashlib
from typing import List, Dict, Any
from .parser_service import ParserService, ParsedCodeUnit

class CodeChunk:
    def __init__(
        self,
        chunk_id: str,
        text_for_embedding: str,
        source_code: str,
        metadata: Dict[str, Any]
    ):
        self.chunk_id = chunk_id
        self.text_for_embedding = text_for_embedding
        self.source_code = source_code
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text_for_embedding,
            "source_code": self.source_code,
            "metadata": self.metadata
        }

class ChunkingService:
    MAX_CHUNK_LINES = 100
    CHUNK_OVERLAP_LINES = 15
    SLIDING_WINDOW_LINES = 60
    SLIDING_OVERLAP = 15

    @classmethod
    def chunk_file(
        cls,
        code: str,
        file_path: str,
        language: str,
        repo_key: str,
        repo_name: str
    ) -> List[CodeChunk]:
        """
        Extracts semantic code units (functions/classes) and falls back to sliding windows for top-level code.
        """
        chunks: List[CodeChunk] = []
        lines = code.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return chunks

        # 1. Parse AST/structural units
        units = ParserService.parse_file(code, language, file_path)
        covered_lines = set()

        for unit in units:
            unit_start = max(1, unit.start_line)
            unit_end = min(total_lines, unit.end_line)
            unit_line_count = unit_end - unit_start + 1

            # Mark lines as covered
            for ln in range(unit_start, unit_end + 1):
                covered_lines.add(ln)

            # If unit is reasonable size, chunk as a single block
            if unit_line_count <= cls.MAX_CHUNK_LINES:
                raw_code = "\n".join(lines[unit_start - 1 : unit_end])
                chunk = cls._create_chunk(
                    raw_code=raw_code,
                    file_path=file_path,
                    language=language,
                    repo_key=repo_key,
                    repo_name=repo_name,
                    start_line=unit_start,
                    end_line=unit_end,
                    function_name=unit.name if unit.unit_type in ("function", "method") else "",
                    class_name=unit.parent_name or (unit.name if unit.unit_type in ("class", "interface", "struct") else ""),
                    unit_type=unit.unit_type
                )
                chunks.append(chunk)
            else:
                # Split large unit with overlap
                for start_idx in range(unit_start - 1, unit_end, cls.MAX_CHUNK_LINES - cls.CHUNK_OVERLAP_LINES):
                    end_idx = min(unit_end, start_idx + cls.MAX_CHUNK_LINES)
                    sub_code = "\n".join(lines[start_idx:end_idx])
                    chunk = cls._create_chunk(
                        raw_code=sub_code,
                        file_path=file_path,
                        language=language,
                        repo_key=repo_key,
                        repo_name=repo_name,
                        start_line=start_idx + 1,
                        end_line=end_idx,
                        function_name=unit.name if unit.unit_type in ("function", "method") else "",
                        class_name=unit.parent_name or (unit.name if unit.unit_type in ("class", "interface", "struct") else ""),
                        unit_type=unit.unit_type
                    )
                    chunks.append(chunk)

        # 2. Window through uncovered lines (top-level declarations, imports, configs)
        # If no units were found or if significant uncovered code exists:
        if len(covered_lines) < total_lines * 0.7 or len(units) == 0:
            for start_idx in range(0, total_lines, cls.SLIDING_WINDOW_LINES - cls.SLIDING_OVERLAP):
                end_idx = min(total_lines, start_idx + cls.SLIDING_WINDOW_LINES)
                window_lines = set(range(start_idx + 1, end_idx + 1))
                
                # Check if this window contains mostly uncovered lines or if total units is 0
                if len(units) == 0 or len(window_lines - covered_lines) > (len(window_lines) // 2):
                    raw_code = "\n".join(lines[start_idx:end_idx])
                    if raw_code.strip():
                        chunk = cls._create_chunk(
                            raw_code=raw_code,
                            file_path=file_path,
                            language=language,
                            repo_key=repo_key,
                            repo_name=repo_name,
                            start_line=start_idx + 1,
                            end_line=end_idx,
                            function_name="",
                            class_name="",
                            unit_type="module_segment"
                        )
                        chunks.append(chunk)

        return chunks

    @classmethod
    def _create_chunk(
        cls,
        raw_code: str,
        file_path: str,
        language: str,
        repo_key: str,
        repo_name: str,
        start_line: int,
        end_line: int,
        function_name: str = "",
        class_name: str = "",
        unit_type: str = "code_block"
    ) -> CodeChunk:
        # Create semantic context header for embedding
        header_parts = [
            f"Repository: {repo_name}",
            f"File: {file_path}",
            f"Language: {language}",
            f"Lines: {start_line}-{end_line}"
        ]
        if class_name:
            header_parts.append(f"Class: {class_name}")
        if function_name:
            header_parts.append(f"Function: {function_name}")
            
        header = f"// Context: {', '.join(header_parts)}\n"
        text_for_embedding = f"{header}{raw_code}"

        # Deterministic unique chunk ID
        raw_id_str = f"{repo_key}:{file_path}:{start_line}:{end_line}:{function_name}"
        chunk_hash = hashlib.sha256(raw_id_str.encode("utf-8")).hexdigest()[:16]
        chunk_id = f"{repo_key}_{chunk_hash}"

        metadata = {
            "repository": repo_key,
            "repo_name": repo_name,
            "file_path": file_path,
            "language": language,
            "function_name": function_name,
            "class_name": class_name,
            "start_line": int(start_line),
            "end_line": int(end_line),
            "unit_type": unit_type,
            "source_code": raw_code
        }

        return CodeChunk(
            chunk_id=chunk_id,
            text_for_embedding=text_for_embedding,
            source_code=raw_code,
            metadata=metadata
        )
