import os
from pathlib import Path
from dotenv import load_dotenv

# Find root and backend .env
current_file = Path(__file__).resolve()
backend_dir = current_file.parent.parent
root_dir = backend_dir.parent

load_dotenv(backend_dir / ".env")
load_dotenv(root_dir / ".env")

class Settings:
    PROJECT_NAME: str = "Codebase RAG Assistant"
    VERSION: str = "1.0.0"
    
    # API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    
    # Models
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-3.6-flash")
    FALLBACK_LLM_MODEL: str = "gemini-3.5-flash"
    
    # Paths
    BASE_DATA_DIR: Path = backend_dir / "data"
    REPOS_DIR: Path = BASE_DATA_DIR / "repos"
    CHROMA_DIR: Path = BASE_DATA_DIR / "chroma"
    
    # Max file size to index (e.g. 500 KB per source file to avoid minified bundles)
    MAX_FILE_SIZE_BYTES: int = 500 * 1024
    
    # Supported language extensions
    SUPPORTED_EXTENSIONS: dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mts": "typescript",
        ".cts": "typescript",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".hh": "cpp",
        ".hxx": "cpp",
        ".go": "go",
    }
    
    # Directories and files to always ignore
    IGNORED_DIRS: set[str] = {
        ".git",
        "node_modules",
        "vendor",
        "build",
        "dist",
        "target",
        ".next",
        "__pycache__",
        "venv",
        ".venv",
        "backend_venv",
        "out",
        "coverage",
        ".idea",
        ".vscode",
        "bin",
        "obj",
        ".gradle",
        ".mvn",
        ".cargo",
        "Pods",
        "DerivedData"
    }
    
    IGNORED_EXTENSIONS: set[str] = {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
        ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z",
        ".exe", ".dll", ".so", ".dylib", ".bin",
        ".class", ".pyc", ".pyo", ".pyd", ".o", ".a",
        ".woff", ".woff2", ".ttf", ".eot", ".otf",
        ".mp4", ".mp3", ".wav", ".avi", ".mov",
        ".lock", ".map", ".min.js", ".min.css"
    }

settings = Settings()

# Ensure directories exist
settings.REPOS_DIR.mkdir(parents=True, exist_ok=True)
settings.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
