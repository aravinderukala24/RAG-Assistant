from fastapi import APIRouter, HTTPException
from ..models.schemas import ChatRequest, ChatResponse
from ..services.rag_service import RAGService

router = APIRouter(prefix="/api/chat", tags=["Chat"])
rag_service = RAGService()

@router.post("", response_model=ChatResponse)
async def chat_with_codebase(request: ChatRequest):
    """
    Retrieves relevant code chunks and generates grounded answer with file/function citations and trace flow.
    """
    try:
        response = rag_service.answer_question(
            repo_identifier=request.repository,
            question=request.question,
            top_k=request.top_k or 6
        )
        return response
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process codebase query: {str(e)}")
