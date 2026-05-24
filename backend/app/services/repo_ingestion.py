import hashlib
import os
import shutil
import stat
import time
from pathlib import Path

from git import Repo

from app.config import settings
from app.services.code_parser import CodeParser
from app.utils.github import normalize_repo_url, parse_github_url


def _on_rm_error(func, path, exc_info):
    """Clear read-only files on Windows (common with OneDrive/git)."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _safe_rmtree(path: Path, retries: int = 5) -> None:
    """Remove directory tree; retry for Windows/OneDrive file locks."""
    if not path.exists():
        return
    for attempt in range(retries):
        try:
            shutil.rmtree(path, onerror=_on_rm_error)
            if not path.exists():
                return
        except OSError:
            pass
        time.sleep(0.3 * (attempt + 1))
    if path.exists():
        raise RuntimeError(
            f"Could not remove existing repo directory: {path}. "
            "Close any programs using it, or delete the folder manually and retry."
        )


class RepoIngestionService:
    """Clone and index GitHub repositories."""

    def __init__(self) -> None:
        self.parser = CodeParser()

    def repo_id_from_url(self, url: str) -> str:
        owner, repo = parse_github_url(url)
        return hashlib.sha256(f"{owner}/{repo}".encode()).hexdigest()[:16]

    def get_repo_path(self, repo_id: str) -> Path:
        return settings.repos_path / repo_id

    def clear_repo_cache(self, repo_id: str) -> None:
        """Remove cached clone and vector data for a repo."""
        _safe_rmtree(self.get_repo_path(repo_id))
        vs_dir = settings.vectorstore_path / repo_id
        _safe_rmtree(vs_dir)

    async def clone_repository(
        self,
        repo_url: str,
        branch: str = "main",
    ) -> tuple[str, Path]:
        normalized = normalize_repo_url(repo_url)
        owner, repo_name = parse_github_url(normalized)
        repo_id = self.repo_id_from_url(normalized)
        dest = self.get_repo_path(repo_id)
        settings.repos_path.mkdir(parents=True, exist_ok=True)

        clone_url = normalized if not settings.github_token else (
            f"https://{settings.github_token}@github.com/{owner}/{repo_name}.git"
        )

        # Deduplicate while preserving order (prefer main over master)
        seen: set[str] = set()
        branches_to_try: list[str] = []
        for b in [branch, "main", "master"]:
            if b and b not in seen:
                seen.add(b)
                branches_to_try.append(b)

        last_error: Exception | None = None

        for b in branches_to_try:
            _safe_rmtree(dest)
            try:
                # Git clone requires a non-existent target path
                Repo.clone_from(clone_url, str(dest), branch=b, depth=1)
                return repo_id, dest
            except Exception as e:
                last_error = e
                _safe_rmtree(dest)

        raise RuntimeError(f"Failed to clone repository: {last_error}")

    def parse_repository(self, repo_path: Path) -> dict:
        return self.parser.analyze(repo_path)

    def get_readme_context(self, repo_path: Path) -> str:
        return self.parser.read_key_files(repo_path)
