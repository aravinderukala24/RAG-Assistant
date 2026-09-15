from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .models.schemas import HealthResponse
from .routes import repositories, chat

app = FastAPI(
    title="Codebase RAG Assistant API",
    description="Backend service for semantic codebase search, multi-language AST chunking, and grounded code reasoning.",
    version=settings.VERSION
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev; in production can be restricted to frontend host
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(repositories.router)
app.include_router(chat.router)

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        gemini_configured=bool(settings.GEMINI_API_KEY)
    )

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to Codebase RAG Assistant API",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
