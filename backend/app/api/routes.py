import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import (
    AnalysisResult,
    AnalysisStatus,
    ChatRequest,
    PRReviewRequest,
    RepoAnalyzeRequest,
    RepoMetadata,
    AgentActivityEvent,
)
from app.config import settings
from app.services.repo_ingestion import RepoIngestionService
from app.services.chat_service import ChatService
from app.services.analysis_store import store
from app.vectorstore.faiss_store import FaissVectorStore
from app.workflows.full_analysis import FullAnalysisWorkflow
from app.agents.gitagent_client import GitAgentClient
from app.utils.github import normalize_repo_url, parse_github_url

router = APIRouter()

_activity_subscribers: dict[str, list[asyncio.Queue]] = {}


def _get_analysis(repo_id: str) -> AnalysisResult:
    result = store.get(repo_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found. The server may have restarted — please analyze again.",
        )
    return result


def _persist(result: AnalysisResult) -> None:
    store.save(result)


async def _publish_activity(repo_id: str, event: AgentActivityEvent) -> None:
    result = store.get(repo_id)
    if result:
        result.activities.append(event)
        _persist(result)
    if repo_id in _activity_subscribers:
        for queue in _activity_subscribers[repo_id]:
            await queue.put(event.model_dump(mode="json"))


async def _run_analysis_pipeline(repo_id: str, repo_url: str, branch: str) -> None:
    ingestion = RepoIngestionService()
    workflow = FullAnalysisWorkflow()
    result = store.get(repo_id)
    if result is None:
        return

    try:
        result.status = AnalysisStatus.CLONING
        _persist(result)
        await _publish_activity(repo_id, AgentActivityEvent(
            agent="system", status="running", message="Cloning repository..."
        ))

        _, repo_path = await ingestion.clone_repository(repo_url, branch)

        result.status = AnalysisStatus.INDEXING
        _persist(result)
        await _publish_activity(repo_id, AgentActivityEvent(
            agent="system", status="running", message="Parsing codebase and building embeddings..."
        ))

        parsed = ingestion.parse_repository(repo_path)
        owner, repo_name = parse_github_url(repo_url)
        metadata = RepoMetadata(
            name=repo_name,
            url=normalize_repo_url(repo_url),
            **parsed,
        )
        result.metadata = metadata

        readme = ingestion.get_readme_context(repo_path)
        vectorstore = FaissVectorStore(repo_id)
        chunk_count = vectorstore.index_repository(repo_path)

        await _publish_activity(repo_id, AgentActivityEvent(
            agent="system", status="completed",
            message=f"Indexed {chunk_count} code chunks"
        ))

        result.status = AnalysisStatus.ANALYZING
        _persist(result)

        async def on_activity(event: AgentActivityEvent) -> None:
            await _publish_activity(repo_id, event)

        await workflow.execute(
            result=result,
            metadata=metadata,
            readme=readme,
            vectorstore=vectorstore,
            repo_path=str(repo_path),
            on_activity=on_activity,
        )
        _persist(result)

    except Exception as e:
        result.status = AnalysisStatus.FAILED
        result.error = str(e)
        _persist(result)
        await _publish_activity(repo_id, AgentActivityEvent(
            agent="system", status="failed", message=str(e)
        ))


@router.get("/health")
async def health() -> dict[str, str]:
    client = GitAgentClient()
    runner_ok = await client.is_runner_available()
    has_key = bool(settings.openai_api_key)
    return {
        "status": "healthy" if has_key else "degraded",
        "openai_configured": str(has_key).lower(),
        "gitagent_runner": "connected" if runner_ok else "openai (git-native prompts)",
    }


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_repo(
    request: RepoAnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> AnalysisResult:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=400,
            detail="OPENAI_API_KEY is not set. Add it to .env in the project root.",
        )

    ingestion = RepoIngestionService()
    repo_url = normalize_repo_url(request.repo_url)
    repo_id = ingestion.repo_id_from_url(repo_url)

    existing = store.get(repo_id)
    if existing and existing.status == AnalysisStatus.COMPLETED:
        return existing
    if (
        existing
        and not request.force
        and existing.status
        in (
            AnalysisStatus.PENDING,
            AnalysisStatus.CLONING,
            AnalysisStatus.INDEXING,
            AnalysisStatus.ANALYZING,
        )
    ):
        return existing

    if request.force and existing:
        try:
            ingestion.clear_repo_cache(repo_id)
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

    if existing and existing.status == AnalysisStatus.FAILED:
        try:
            ingestion.clear_repo_cache(repo_id)
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
    elif not existing:
        try:
            ingestion.clear_repo_cache(repo_id)
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

    result = AnalysisResult(
        repo_id=repo_id,
        status=AnalysisStatus.PENDING,
    )
    store.set(result)
    _activity_subscribers.setdefault(repo_id, [])

    background_tasks.add_task(
        _run_analysis_pipeline,
        repo_id,
        repo_url,
        request.branch,
    )

    return result


@router.get("/analyze/{repo_id}", response_model=AnalysisResult)
async def get_analysis(repo_id: str) -> AnalysisResult:
    return _get_analysis(repo_id)


@router.get("/analyze/{repo_id}/stream")
async def stream_activity(repo_id: str):
    _get_analysis(repo_id)
    queue: asyncio.Queue = asyncio.Queue()
    _activity_subscribers.setdefault(repo_id, []).append(queue)

    async def event_generator():
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=120.0)
                yield {"event": "activity", "data": event}
                analysis = store.get(repo_id)
                if analysis and analysis.status in (
                    AnalysisStatus.COMPLETED,
                    AnalysisStatus.FAILED,
                ):
                    yield {"event": "complete", "data": {"status": analysis.status}}
                    break
        except asyncio.TimeoutError:
            yield {"event": "timeout", "data": {"message": "Stream timeout"}}

    return EventSourceResponse(event_generator())


@router.post("/chat")
async def chat(request: ChatRequest) -> dict[str, Any]:
    _get_analysis(request.repo_id)
    service = ChatService()
    return await service.ask(request.repo_id, request.message, request.top_k)


@router.post("/pr-review")
async def pr_review(request: PRReviewRequest) -> dict[str, str]:
    _get_analysis(request.repo_id)
    client = GitAgentClient()
    prompt = f"""Review this pull request/code change:

**Title:** {request.title}

**Diff/Code:**
```
{request.diff[:12000]}
```

Provide a thorough PR review following your standard format."""

    content, duration_ms = await client.run_agent(
        agent_name="pr-review",
        prompt=prompt,
        context="",
    )
    return {"review": content, "duration_ms": str(duration_ms)}


@router.get("/agents")
async def list_agents() -> dict[str, Any]:
    from app.agents.prompt_loader import PromptLoader
    loader = PromptLoader()
    client = GitAgentClient()
    return {
        "agents": loader.list_agents(),
        "runner_available": await client.is_runner_available(),
        "workflow": "full-analysis",
    }
