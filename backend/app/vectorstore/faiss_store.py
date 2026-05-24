import json
import pickle
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from openai import OpenAI

from app.config import settings


class FaissVectorStore:
    """FAISS-backed vector store with OpenAI embeddings."""

    def __init__(self, repo_id: str) -> None:
        self.repo_id = repo_id
        self.store_dir = settings.vectorstore_path / repo_id
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.store_dir / "index.faiss"
        self.meta_path = self.store_dir / "metadata.pkl"
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.index: faiss.IndexFlatL2 | None = None
        self.metadata: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.index_path.exists() and self.meta_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            with open(self.meta_path, "rb") as f:
                self.metadata = pickle.load(f)

    def _save(self) -> None:
        if self.index is not None:
            faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, "wb") as f:
            pickle.dump(self.metadata, f)

    def _embed(self, texts: list[str]) -> np.ndarray:
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY required for embeddings")
        response = self.client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
        )
        vectors = [item.embedding for item in response.data]
        arr = np.array(vectors, dtype=np.float32)
        faiss.normalize_L2(arr)
        return arr

    def index_repository(self, repo_path: Path, chunk_size: int = 1500, overlap: int = 200) -> int:
        chunks: list[dict[str, Any]] = []
        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "dist", "build", ".next",
            "docs", "doc", "website", "test", "tests", "__tests__", "examples",
            ".github", "assets", "img", "images",
        }
        max_files = settings.max_index_files
        max_chunks = settings.max_index_chunks
        files_seen = 0

        for fpath in sorted(repo_path.rglob("*")):
            if files_seen >= max_files or len(chunks) >= max_chunks:
                break
            if not fpath.is_file():
                continue
            if any(p in fpath.parts for p in skip_dirs):
                continue
            if fpath.suffix.lower() not in {
                ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
                ".yaml", ".yml", ".json", ".sql", ".sh", ".rb", ".php",
            }:
                continue
            files_seen += 1
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if len(content.strip()) < 50:
                continue

            rel_path = str(fpath.relative_to(repo_path)).replace("\\", "/")
            for i in range(0, len(content), chunk_size - overlap):
                chunk_text = content[i : i + chunk_size]
                if len(chunk_text.strip()) < 30:
                    continue
                chunks.append({
                    "file": rel_path,
                    "content": chunk_text,
                    "start": i,
                })
                if len(chunks) >= max_chunks:
                    break

        if not chunks:
            return 0

        batch_size = 50
        all_vectors: list[np.ndarray] = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [f"File: {c['file']}\n{c['content']}" for c in batch]
            vectors = self._embed(texts)
            all_vectors.append(vectors)

        combined = np.vstack(all_vectors)
        dim = combined.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(combined)
        self.metadata = chunks
        self._save()
        return len(chunks)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if self.index is None or not self.metadata:
            return []
        query_vec = self._embed([query])
        scores, indices = self.index.search(query_vec, min(top_k, len(self.metadata)))
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = self.metadata[idx]
            results.append({
                "file": meta["file"],
                "content": meta["content"],
                "score": float(score),
            })
        return results
