import os
import re
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from ..config import settings
from ..models.schemas import RepoFileNode

class GitHubService:
    @staticmethod
    def parse_repo_url(url: str) -> Tuple[str, str, str]:
        """
        Parses GitHub URL into (normalized_url, repo_key, repo_name)
        Accepts:
          - https://github.com/owner/repo
          - https://github.com/owner/repo.git
          - owner/repo
        """
        clean_url = url.strip().rstrip("/")
        if clean_url.endswith(".git"):
            clean_url = clean_url[:-4]
            
        # Match github.com/owner/repo pattern
        match = re.search(r"github\.com[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", clean_url)
        if match:
            owner, repo = match.group(1), match.group(2)
            normalized_url = f"https://github.com/{owner}/{repo}.git"
            repo_key = f"{owner}__{repo}".lower().replace(".", "_")
            repo_name = f"{owner}/{repo}"
            return normalized_url, repo_key, repo_name
        
        # Match owner/repo pattern
        match_short = re.match(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$", clean_url)
        if match_short:
            owner, repo = match_short.group(1), match_short.group(2)
            normalized_url = f"https://github.com/{owner}/{repo}.git"
            repo_key = f"{owner}__{repo}".lower().replace(".", "_")
            repo_name = f"{owner}/{repo}"
            return normalized_url, repo_key, repo_name
            
        raise ValueError(f"Invalid GitHub URL: '{url}'. Expected format: https://github.com/owner/repo")

    @staticmethod
    def clone_or_update_repo(repo_url: str) -> Tuple[Path, str, str]:
        """
        Clones public repo with --depth 1 to local storage.
        Returns (repo_path, repo_key, repo_name)
        """
        normalized_url, repo_key, repo_name = GitHubService.parse_repo_url(repo_url)
        repo_dir = settings.REPOS_DIR / repo_key
        
        if repo_dir.exists():
            # If repo already exists, we can re-use it or do a pull
            try:
                subprocess.run(
                    ["git", "pull", "--depth", "1"],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False
                )
                return repo_dir, repo_key, repo_name
            except Exception:
                # If pull fails, re-clone fresh
                shutil.rmtree(repo_dir, ignore_errors=True)

        # Clone fresh
        cmd = ["git", "clone", "--depth", "1", normalized_url, str(repo_dir)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                # Provide helpful error message
                err = result.stderr.strip() or result.stdout.strip()
                if "Authentication failed" in err or "Repository not found" in err:
                    raise ValueError(f"Could not access repository '{repo_name}'. Please ensure it is public and exists.")
                raise RuntimeError(f"Git clone failed: {err}")
        except subprocess.TimeoutExpired:
            shutil.rmtree(repo_dir, ignore_errors=True)
            raise TimeoutError("Repository cloning timed out (took > 2 minutes).")

        return repo_dir, repo_key, repo_name

    @staticmethod
    def scan_source_files(repo_dir: Path) -> List[Dict[str, any]]:
        """
        Scans repository directory and returns list of valid source files with metadata.
        Filters out ignored directories and non-source extensions.
        """
        source_files = []
        
        for root, dirs, files in os.walk(repo_dir):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in settings.IGNORED_DIRS and not d.startswith(".")]
            
            for file in files:
                file_path = Path(root) / file
                
                # Check extension
                ext = file_path.suffix.lower()
                if ext not in settings.SUPPORTED_EXTENSIONS:
                    continue
                    
                # Skip files with ignored extensions
                if any(file.endswith(ign) for ign in settings.IGNORED_EXTENSIONS):
                    continue
                    
                # Check size
                try:
                    size = file_path.stat().st_size
                    if size == 0 or size > settings.MAX_FILE_SIZE_BYTES:
                        continue
                except OSError:
                    continue
                    
                # Relative path from repository root
                rel_path = file_path.relative_to(repo_dir).as_posix()
                lang = settings.SUPPORTED_EXTENSIONS[ext]
                
                source_files.append({
                    "full_path": file_path,
                    "relative_path": rel_path,
                    "language": lang,
                    "extension": ext,
                    "size": size
                })
                
        return source_files

    @staticmethod
    def get_repo_tree(repo_dir: Path) -> List[RepoFileNode]:
        """
        Generates a nested tree structure of files for the frontend file explorer.
        """
        def build_node(current_path: Path) -> Optional[RepoFileNode]:
            rel = current_path.relative_to(repo_dir).as_posix()
            name = current_path.name
            
            if current_path.is_dir():
                if name in settings.IGNORED_DIRS or name.startswith("."):
                    return None
                children = []
                try:
                    for child in sorted(current_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                        child_node = build_node(child)
                        if child_node:
                            children.append(child_node)
                except PermissionError:
                    return None
                
                # Only include directories that have non-empty children or relevant files
                if not children:
                    return None
                return RepoFileNode(
                    name=name,
                    path=rel,
                    type="directory",
                    children=children
                )
            else:
                ext = current_path.suffix.lower()
                lang = settings.SUPPORTED_EXTENSIONS.get(ext)
                if not lang:
                    return None
                return RepoFileNode(
                    name=name,
                    path=rel,
                    type="file",
                    language=lang,
                    size=current_path.stat().st_size if current_path.exists() else 0
                )

        root_nodes = []
        for item in sorted(repo_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            node = build_node(item)
            if node:
                root_nodes.append(node)
        return root_nodes

    @staticmethod
    def read_file_content(repo_dir: Path, relative_path: str) -> str:
        """
        Reads raw file content safely.
        """
        # Protect against path traversal
        clean_rel = Path(relative_path).as_posix().lstrip("/\\")
        target_path = (repo_dir / clean_rel).resolve()
        
        if not str(target_path).startswith(str(repo_dir.resolve())):
            raise PermissionError("Access outside repository path is denied")
            
        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"File '{relative_path}' not found")
            
        try:
            return target_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raise RuntimeError(f"Error reading file {relative_path}: {e}")
