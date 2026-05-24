from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class AgentRole(str, Enum):
    ARCHITECT = "architect"
    BUG_HUNTER = "bug-hunter"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    TASK_PLANNER = "task-planner"
    SECURITY = "security"
    PR_REVIEW = "pr-review"
    ORCHESTRATOR = "orchestrator"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    CLONING = "cloning"
    INDEXING = "indexing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class RepoAnalyzeRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL")
    branch: str = Field(default="main", description="Branch to analyze")
    force: bool = Field(default=False, description="Restart even if analysis is in progress")


class ChatRequest(BaseModel):
    repo_id: str
    message: str
    top_k: int = Field(default=5, ge=1, le=20)


class PRReviewRequest(BaseModel):
    repo_id: str
    diff: str = Field(..., description="Git diff or code snippet to review")
    title: str = Field(default="Code Review")


class AgentActivityEvent(BaseModel):
    agent: str
    status: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    output_preview: str | None = None


class RepoMetadata(BaseModel):
    name: str
    url: str
    languages: dict[str, int] = Field(default_factory=dict)
    frameworks: list[str] = Field(default_factory=list)
    file_count: int = 0
    total_lines: int = 0
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    folder_structure: list[str] = Field(default_factory=list)
    complexity_hotspots: list[dict[str, Any]] = Field(default_factory=list)


class AgentOutput(BaseModel):
    role: str
    content: str
    duration_ms: int = 0


class AnalysisResult(BaseModel):
    repo_id: str
    status: AnalysisStatus
    metadata: RepoMetadata | None = None
    architecture: str | None = None
    bugs: str | None = None
    security: str | None = None
    refactor: str | None = None
    documentation: str | None = None
    tasks: str | None = None
    pr_guidelines: str | None = None
    health_score: int | None = None
    tech_debt_score: int | None = None
    mermaid_diagram: str | None = None
    changelog: str | None = None
    dependency_risks: list[dict[str, Any]] = Field(default_factory=list)
    agent_outputs: list[AgentOutput] = Field(default_factory=list)
    activities: list[AgentActivityEvent] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
