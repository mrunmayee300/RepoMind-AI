import json
from pathlib import Path

from app.config import settings
from app.models.schemas import AnalysisResult, AnalysisStatus


class AnalysisStore:
    """Persist analysis results to disk so they survive server reloads."""

    def __init__(self) -> None:
        self._cache: dict[str, AnalysisResult] = {}
        self.store_dir = settings.analyses_path
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> None:
        self._cache.clear()
        for path in self.store_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                result = AnalysisResult.model_validate(data)
                # Stale in-flight jobs cannot resume after reload
                if result.status in (
                    AnalysisStatus.PENDING,
                    AnalysisStatus.CLONING,
                    AnalysisStatus.INDEXING,
                    AnalysisStatus.ANALYZING,
                ):
                    result.status = AnalysisStatus.FAILED
                    result.error = (
                        "Analysis interrupted (server restarted). "
                        "Please run Analyze again from the dashboard."
                    )
                    self.save(result)
                self._cache[result.repo_id] = result
            except (json.JSONDecodeError, OSError, ValueError):
                continue

    def get(self, repo_id: str) -> AnalysisResult | None:
        if repo_id in self._cache:
            return self._cache[repo_id]
        path = self._path(repo_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result = AnalysisResult.model_validate(data)
            self._cache[repo_id] = result
            return result
        except (json.JSONDecodeError, OSError, ValueError):
            return None

    def set(self, result: AnalysisResult) -> None:
        self._cache[result.repo_id] = result
        self.save(result)

    def save(self, result: AnalysisResult) -> None:
        self._cache[result.repo_id] = result
        path = self._path(result.repo_id)
        payload = result.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def delete(self, repo_id: str) -> None:
        self._cache.pop(repo_id, None)
        path = self._path(repo_id)
        if path.exists():
            path.unlink()

    def _path(self, repo_id: str) -> Path:
        return self.store_dir / f"{repo_id}.json"


store = AnalysisStore()
