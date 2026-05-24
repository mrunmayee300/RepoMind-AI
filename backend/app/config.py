from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    github_token: str = ""
    agent_runner_url: str = "http://localhost:4000"
    agents_root: str = "./agents"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    repos_cache_dir: str = "./data/repos"
    vectorstore_dir: str = "./data/vectorstores"
    analyses_dir: str = "./data/analyses"
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"
    use_gitagent_runner: bool = False  # env: USE_GITAGENT_RUNNER=true to enable GitClaw sidecar
    max_index_files: int = 120
    max_index_chunks: int = 200
    max_agent_context_chars: int = 12000

    @property
    def project_root(self) -> Path:
        """Repo root (parent of backend/)."""
        return Path(__file__).resolve().parents[2]

    @property
    def agents_path(self) -> Path:
        p = Path(self.agents_root)
        if p.is_absolute():
            return p
        return (self.project_root / p).resolve()

    @property
    def repos_path(self) -> Path:
        p = Path(self.repos_cache_dir)
        if not p.is_absolute():
            p = self.project_root / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def vectorstore_path(self) -> Path:
        p = Path(self.vectorstore_dir)
        if not p.is_absolute():
            p = self.project_root / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def analyses_path(self) -> Path:
        p = Path(self.analyses_dir)
        if not p.is_absolute():
            p = self.project_root / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
