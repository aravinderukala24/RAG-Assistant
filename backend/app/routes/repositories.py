import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from ..models.schemas import AnalyzeRequest, AnalyzeResponse, RepoTreeResponse, FileContentResponse
from ..services.rag_service import RAGService
from ..services.github_service import GitHubService
from ..config import settings

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])
rag_service = RAGService()
github_service = GitHubService()


def _sse_event_generator(repo_url: str):
    """
    Wraps the RAG service's streaming pipeline into SSE-formatted text chunks.
    Each event is: data: <json>\n\n
    """
    try:
        for event in rag_service.analyze_repository_stream(repo_url):
            yield f"data: {json.dumps(event)}\n\n"
    except Exception as e:
        error_event = {
            "stage": "error",
            "status": f"Failed to analyze repository: {str(e)}",
            "progress": 0,
        }
        yield f"data: {json.dumps(error_event)}\n\n"


@router.post("/analyze")
async def analyze_repository(request: AnalyzeRequest):
    """
    Ingests, parses, chunks, and indexes a public GitHub repository.
    Returns a Server-Sent Events stream with real-time progress updates.
    """
    return StreamingResponse(
        _sse_event_generator(request.repo_url),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tree", response_model=RepoTreeResponse)
async def get_repository_tree(repository: str = Query(..., description="Repository key or name")):
    """
    Returns the file hierarchy of an indexed repository for the UI file explorer.
    """
    try:
        if "github.com" in repository or "/" in repository:
            _, repo_key, repo_name = github_service.parse_repo_url(repository)
        else:
            repo_key = repository
            repo_name = repository.replace("__", "/")

        repo_dir = settings.REPOS_DIR / repo_key
        if not repo_dir.exists():
            raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found locally. Please analyze it first.")

        tree = github_service.get_repo_tree(repo_dir)
        return RepoTreeResponse(repository=repo_name, tree=tree)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load repository tree: {str(e)}")


@router.get("/file", response_model=FileContentResponse)
async def get_file_content(
    repository: str = Query(..., description="Repository key or name"),
    file_path: str = Query(..., description="Relative file path")
):
    """
    Fetches raw source file content for citation preview and line highlighting.
    """
    try:
        if "github.com" in repository or "/" in repository:
            _, repo_key, repo_name = github_service.parse_repo_url(repository)
        else:
            repo_key = repository
            repo_name = repository.replace("__", "/")

        repo_dir = settings.REPOS_DIR / repo_key
        if not repo_dir.exists():
            raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found locally.")

        content = github_service.read_file_content(repo_dir, file_path)
        ext = "." + file_path.split(".")[-1].lower() if "." in file_path else ""
        lang = settings.SUPPORTED_EXTENSIONS.get(ext, "text")

        return FileContentResponse(
            repository=repo_name,
            file_path=file_path,
            content=content,
            language=lang
        )
    except FileNotFoundError as fe:
        raise HTTPException(status_code=404, detail=str(fe))
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
