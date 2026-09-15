import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.services.parser_service import ParserService
from app.services.chunking_service import ChunkingService
from app.services.vector_service import VectorService
from app.services.github_service import GitHubService

def test_python_parsing():
    sample_py = """import os

class AuthService:
    \"\"\"Handles user authentication.\"\"\"
    def __init__(self, secret: str):
        self.secret = secret

    def authenticate_user(self, username: str, password_hash: str) -> bool:
        # Check password hash
        if username == "admin":
            return True
        return False

def generate_jwt(user_id: str) -> str:
    return f"token_{user_id}"
"""
    units = ParserService.parse_python(sample_py, "auth.py")
    print(f"[*] Python AST parsed {len(units)} units:")
    for u in units:
        print(f"    - {u.unit_type}: {u.name} (Lines {u.start_line}-{u.end_line})")
    assert len(units) >= 3, f"Expected at least 3 units, got {len(units)}"
    names = [u.name for u in units]
    assert "AuthService" in names
    assert "authenticate_user" in names
    assert "generate_jwt" in names
    print("[PASS] Python AST parsing test passed!")

def test_typescript_parsing():
    sample_ts = """export interface User {
  id: string;
  name: string;
}

export class UserService {
  async getUser(id: string): Promise<User> {
    const user = await db.find(id);
    return user;
  }
}

export const validatePassword = (password: string): boolean => {
  return password.length >= 8;
};
"""
    units = ParserService.parse_structural(sample_ts, "typescript")
    print(f"[*] TypeScript parsed {len(units)} units:")
    for u in units:
        print(f"    - {u.unit_type}: {u.name} (Lines {u.start_line}-{u.end_line})")
    assert len(units) >= 2, f"Expected units for TS, got {len(units)}"
    print("[PASS] TypeScript structural parsing test passed!")

def test_chunking():
    sample_code = """def connect_db():
    return Database("localhost:5432")

class QueryRunner:
    def run(self, sql):
        return db.execute(sql)
"""
    chunks = ChunkingService.chunk_file(
        code=sample_code,
        file_path="src/db.py",
        language="python",
        repo_key="test_repo",
        repo_name="test/repo"
    )
    print(f"[*] Chunking generated {len(chunks)} chunks:")
    for c in chunks:
        print(f"    - Chunk ID: {c.chunk_id}, Func: {c.metadata['function_name']}, Lines: {c.metadata['start_line']}-{c.metadata['end_line']}")
    assert len(chunks) >= 2, f"Expected >= 2 chunks, got {len(chunks)}"
    print("[PASS] Code chunking test passed!")

def test_vector_service():
    vector_service = VectorService()
    test_repo = "test_owner__test_repo"
    
    # Create mock chunks and mock embeddings
    sample_chunk = ChunkingService._create_chunk(
        raw_code="def login(): return True",
        file_path="src/auth.py",
        language="python",
        repo_key=test_repo,
        repo_name="test_owner/test_repo",
        start_line=1,
        end_line=2,
        function_name="login",
        class_name="",
        unit_type="function"
    )
    # 768-dim mock vector
    mock_vector = [0.1] * 768
    
    vector_service.index_chunks(test_repo, [sample_chunk], [mock_vector])
    assert vector_service.is_repo_indexed(test_repo)
    
    results = vector_service.query_similar_chunks(test_repo, mock_vector, top_k=1)
    assert len(results) == 1
    assert results[0]["file_path"] == "src/auth.py"
    assert results[0]["function_name"] == "login"
    print("[PASS] Vector DB insertion and cosine retrieval test passed!")

def test_github_url_parsing():
    cases = [
        ("https://github.com/fastapi/fastapi", "fastapi__fastapi", "fastapi/fastapi"),
        ("https://github.com/pallets/flask.git", "pallets__flask", "pallets/flask"),
        ("vercel/next.js", "vercel__next_js", "vercel/next.js")
    ]
    for url, exp_key, exp_name in cases:
        _, key, name = GitHubService.parse_repo_url(url)
        assert key == exp_key, f"Expected key {exp_key}, got {key}"
        assert name == exp_name, f"Expected name {exp_name}, got {name}"
    print("[PASS] GitHub URL parsing tests passed!")

if __name__ == "__main__":
    print("Running Codebase RAG Backend Tests...")
    test_python_parsing()
    test_typescript_parsing()
    test_chunking()
    test_vector_service()
    test_github_url_parsing()
    print("\nALL BACKEND CORE TESTS PASSED SUCCESSFULLY!")
