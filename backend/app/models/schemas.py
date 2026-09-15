from pydantic import BaseModel, Field
from typing import Optional, List, Any

class AnalyzeRequest(BaseModel):
    repo_url: str = Field(..., description="Public GitHub repository URL (e.g. https://github.com/psf/requests)")

class AnalyzeResponse(BaseModel):
    repository: str
    repo_name: str
    status: str
    files_scanned: int
    chunks_indexed: int
    languages: List[str]
    message: str = "Repository indexed successfully"

class CodeSource(BaseModel):
    file_path: str
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    start_line: int
    end_line: int
    language: str
    snippet: str
    similarity_score: Optional[float] = None

class TraceStep(BaseModel):
    step_number: int
    title: str
    description: str
    file_path: Optional[str] = None
    function_name: Optional[str] = None
    line_range: Optional[str] = None

class ChatRequest(BaseModel):
    repository: str = Field(..., description="Repository identifier (e.g. owner/repo or local key)")
    question: str = Field(..., description="Natural language question about the codebase")
    top_k: Optional[int] = Field(default=6, description="Number of context chunks to retrieve")

class ChatResponse(BaseModel):
    question: str
    repository: str
    answer: str
    sources: List[CodeSource] = []
    trace_flow: List[TraceStep] = []

class RepoFileNode(BaseModel):
    name: str
    path: str
    type: str  # "file" or "directory"
    language: Optional[str] = None
    size: Optional[int] = None
    children: Optional[List["RepoFileNode"]] = None

class RepoTreeResponse(BaseModel):
    repository: str
    tree: List[RepoFileNode]

class FileContentResponse(BaseModel):
    repository: str
    file_path: str
    content: str
    language: str

class HealthResponse(BaseModel):
    status: str
    version: str
    gemini_configured: bool
