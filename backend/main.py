from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv

from app.config import settings
from app.api.routes import router
from app.services.analysis_store import store

_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.agents_path.mkdir(parents=True, exist_ok=True)
    settings.repos_path.mkdir(parents=True, exist_ok=True)
    settings.vectorstore_path.mkdir(parents=True, exist_ok=True)
    settings.analyses_path.mkdir(parents=True, exist_ok=True)
    store.load_all()
    yield


app = FastAPI(
    title="RepoMind AI",
    description="Autonomous GitHub engineering assistant powered by GitAgent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": "RepoMind AI",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
    )
