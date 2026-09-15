# 🔍 Codebase RAG Assistant

> **Understand any GitHub repository in seconds** — AI-powered semantic code search with grounded Q&A, file/function/line citations, and execution trace visualization.

## Problem

Developers frequently need to understand unfamiliar codebases — during onboarding, code reviews, open-source contributions, or debugging. Manually reading through hundreds of files is slow and error-prone.

## Solution

**Codebase RAG Assistant** lets you paste a public GitHub repository URL and immediately ask natural-language questions about the code. Answers are always **grounded in retrieved source code** with precise file, function, and line number citations — never fabricated.

## Features

- **One-Click Repository Indexing** — paste a GitHub URL and the entire codebase is cloned, parsed, chunked, and embedded
- **Multi-Language Support** — Python, JavaScript, TypeScript, Java, C, C++, Go
- **Semantic Code Search** — find relevant code by meaning, not just keywords
- **Grounded Answers** — every response cites exact files, functions, and line ranges
- **Execution Trace Visualization** — see step-by-step code flow diagrams
- **Interactive File Explorer** — browse the indexed repository structure
- **Source Evidence Panel** — view retrieved code snippets with similarity scores

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Next.js Frontend                   │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │   File   │  │     Chat     │  │   Sources &   │  │
│  │ Explorer │  │  Interface   │  │   Evidence    │  │
│  └──────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP/REST
┌─────────────────────▼───────────────────────────────┐
│                 FastAPI Backend                       │
│  ┌─────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐  │
│  │ GitHub  │ │ Parser │ │ Chunking │ │ Embedding│  │
│  │ Service │ │Service │ │ Service  │ │ Service  │  │
│  └────┬────┘ └───┬────┘ └────┬─────┘ └────┬─────┘  │
│       │          │           │             │         │
│  ┌────▼──────────▼───────────▼─────────────▼─────┐  │
│  │              RAG Service                       │  │
│  └────────────────────┬──────────────────────────┘  │
│                       │                              │
│  ┌────────────────────▼──────────────────────────┐  │
│  │         Vector Service (ChromaDB)              │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │         LLM Service (Gemini API)               │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## End-to-End Workflow

1. **User inputs** a public GitHub repository URL
2. **Git clone** with `--depth 1` for speed
3. **File filtering** — skip binaries, images, lockfiles, `node_modules`, etc.
4. **Code parsing** — Python AST parser + structural brace parser for other languages
5. **Semantic chunking** — extract functions, classes, methods with metadata headers
6. **Embedding generation** — batch embed via Gemini `text-embedding-004`
7. **Vector storage** — upsert into ChromaDB with file/function/line metadata
8. **User asks a question**
9. **Query embedding** → **cosine similarity search** in ChromaDB
10. **Top-K retrieval** of relevant code chunks
11. **Grounded LLM generation** — Gemini answers strictly from retrieved context
12. **Structured response** — answer + sources + optional trace flow

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, TypeScript, Tailwind CSS, Lucide Icons |
| Backend | Python 3.14, FastAPI |
| LLM | Google Gemini (gemini-2.5-flash / gemini-1.5-flash) |
| Embeddings | Gemini text-embedding-004 |
| Vector DB | ChromaDB (persistent local storage) |
| Code Parsing | Python AST + structural regex parser |

## Project Structure

```
RAG-Assistant/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── config.py            # Settings & environment
│   │   ├── models/
│   │   │   └── schemas.py       # Pydantic request/response models
│   │   ├── routes/
│   │   │   ├── repositories.py  # /api/repositories/* endpoints
│   │   │   └── chat.py          # /api/chat endpoint
│   │   └── services/
│   │       ├── github_service.py    # Git clone & file scanning
│   │       ├── parser_service.py    # Multi-language code parsing
│   │       ├── chunking_service.py  # Semantic code chunking
│   │       ├── embedding_service.py # Gemini embedding generation
│   │       ├── vector_service.py    # ChromaDB operations
│   │       ├── llm_service.py       # Gemini LLM grounded generation
│   │       └── rag_service.py       # End-to-end RAG orchestration
│   ├── requirements.txt
│   └── test_backend.py
├── frontend/
│   ├── src/app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # Main UI component
│   │   └── globals.css
│   └── package.json
├── .env.example
├── .gitignore
└── README.md
```

## Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Git**
- **Gemini API Key** — get one free at [Google AI Studio](https://aistudio.google.com/app/apikey)

## Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env`:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

## Local Setup & Running

### Backend

```bash
# Create virtual environment
python -m venv backend_venv

# Install dependencies
# Windows:
.\backend_venv\Scripts\pip install -r backend/requirements.txt
# Mac/Linux:
# ./backend_venv/bin/pip install -r backend/requirements.txt

# Run backend server
# Windows:
.\backend_venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# Mac/Linux:
# ./backend_venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Backend will be available at: **http://127.0.0.1:8000**
API docs at: **http://127.0.0.1:8000/docs**

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at: **http://localhost:3000**

## Example Questions

After indexing a repository, try:

- "What is the overall architecture of this project?"
- "Where is authentication handled?"
- "How is the database connection initialized?"
- "Where is the main entry point?"
- "Trace the login flow"
- "Which function validates user input?"
- "What design patterns are used?"
- "How are API routes organized?"

## API Documentation

### `GET /health`
Health check endpoint.

### `POST /api/repositories/analyze`
Clone and index a GitHub repository.

```json
{
  "repo_url": "https://github.com/owner/repo"
}
```

### `POST /api/chat`
Ask a question about an indexed repository.

```json
{
  "repository": "owner__repo",
  "question": "Where is authentication handled?"
}
```

### `GET /api/repositories/tree?repository=owner__repo`
Get repository file hierarchy.

### `GET /api/repositories/file?repository=owner__repo&file_path=src/main.py`
Get raw file content.

## Screenshots

> *Screenshots will be added after demo*

## Limitations

- Public GitHub repositories only
- Large repositories (>5000 files) may take longer to index
- Gemini API rate limits apply to embedding generation
- ChromaDB runs in-process (not a separate server)
- No incremental re-indexing (full re-index on update)

## Future Improvements

- [ ] Private repository support via GitHub tokens
- [ ] Tree-sitter integration for more precise AST parsing
- [ ] Incremental indexing / diff-based updates
- [ ] Multi-repository cross-referencing
- [ ] Code generation and refactoring suggestions
- [ ] Streaming LLM responses
- [ ] Persistent chat history
- [ ] Deployment to Vercel + Railway/Render

## Hackathon Differentiation

1. **True RAG Pipeline** — not just sending entire files to an LLM; uses semantic chunking + embeddings + vector retrieval
2. **Multi-Language Parsing** — AST-level extraction for Python, structural parsing for 6+ languages
3. **Grounded Answers** — every claim cites exact source with file path, function name, and line range
4. **Execution Trace Visualization** — unique flow diagram feature showing code execution paths
5. **Rich Metadata** — every chunk preserves repository, file, language, function, class, and line information
6. **Production-Ready Architecture** — clean separation of concerns, ready for scaling

---

Built for the hackathon using Google Gemini, FastAPI, Next.js, and ChromaDB.
