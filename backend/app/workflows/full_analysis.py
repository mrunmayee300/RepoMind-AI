import re
from datetime import datetime
from typing import Any, Callable, Awaitable

from app.agents.gitagent_client import GitAgentClient
from app.agents.prompt_loader import PromptLoader
from app.models.schemas import (
    AgentActivityEvent,
    AgentOutput,
    AnalysisResult,
    AnalysisStatus,
    RepoMetadata,
)
from app.vectorstore.faiss_store import FaissVectorStore


ActivityCallback = Callable[[AgentActivityEvent], Awaitable[None]]


class FullAnalysisWorkflow:
    """
    Multi-agent orchestration workflow powered by GitAgent definitions.

    Executes agents in sequence per workflows/full-analysis.yaml,
    passing outputs between agents as context.
    """

    AGENT_SEQUENCE = [
        ("architect", "Analyzing system architecture and design patterns..."),
        ("bug-hunter", "Scanning for bugs and suspicious code patterns..."),
        ("security", "Running security audit for secrets and vulnerabilities..."),
        ("refactor", "Identifying refactoring opportunities and tech debt..."),
        ("documentation", "Generating onboarding guide and documentation..."),
        ("task-planner", "Creating actionable GitHub issues and sprint tasks..."),
        ("pr-review", "Generating PR review guidelines and checklist..."),
    ]

    def __init__(self) -> None:
        self.client = GitAgentClient()
        self.prompt_loader = PromptLoader()

    def _build_repo_context(
        self,
        metadata: RepoMetadata,
        readme: str,
        code_snippets: list[dict[str, Any]],
    ) -> str:
        lines = [
            f"# Repository: {metadata.name}",
            f"URL: {metadata.url}",
            f"Files: {metadata.file_count} | Lines: {metadata.total_lines}",
            "",
            "## Languages",
            ", ".join(f"{k}: {v} lines" for k, v in metadata.languages.items()),
            "",
            "## Frameworks",
            ", ".join(metadata.frameworks) or "None detected",
            "",
            "## Folder Structure",
            "\n".join(f"- {f}" for f in metadata.folder_structure[:30]),
            "",
            "## Complexity Hotspots",
        ]
        for h in metadata.complexity_hotspots[:5]:
            lines.append(f"- {h['file']} ({h['lines']} lines)")

        if metadata.dependencies:
            lines.append("\n## Dependencies")
            for mgr, deps in metadata.dependencies.items():
                lines.append(f"### {mgr}")
                lines.append(", ".join(deps[:15]))

        if readme:
            lines.append(f"\n## Key Files\n{readme[:4000]}")

        if code_snippets:
            lines.append("\n## Relevant Code Snippets")
            for snip in code_snippets[:8]:
                lines.append(f"\n### {snip['file']}\n```\n{snip['content'][:800]}\n```")

        return "\n".join(lines)

    def _get_agent_prompt(self, agent_name: str, prior_outputs: dict[str, str]) -> str:
        workflow = self.prompt_loader.load_workflow("full-analysis")
        for step in workflow.get("steps", []):
            if step.get("agent") == agent_name:
                base = step.get("prompt", f"Analyze the repository as {agent_name}.")
                inputs = step.get("input_from", [])
                if isinstance(inputs, str):
                    inputs = [inputs]
                if inputs:
                    context_parts = []
                    for key in inputs:
                        if key in prior_outputs:
                            context_parts.append(f"## Prior: {key}\n{prior_outputs[key][:3000]}")
                    if context_parts:
                        base += "\n\n" + "\n\n".join(context_parts)
                return base
        return f"Perform your specialist analysis as the {agent_name} agent."

    def _extract_mermaid(self, architecture: str) -> str | None:
        if not architecture:
            return None
        patterns = [
            r"```mermaid\s*\n([\s\S]*?)```",
            r"```\s*mermaid\s*\n([\s\S]*?)```",
        ]
        for pattern in patterns:
            match = re.search(pattern, architecture, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        # Bare diagram block (flowchart/graph/etc. without fences)
        bare = re.search(
            r"(?:(?:^|\n)(flowchart|graph|sequenceDiagram|classDiagram|erDiagram|C4Context)[\s\S]{10,2000})",
            architecture,
            re.IGNORECASE,
        )
        if bare:
            return bare.group(1).strip()
        return None

    def _compute_health_score(
        self,
        bugs: str,
        security: str,
        refactor: str,
    ) -> int:
        score = 85
        critical_bugs = bugs.lower().count("critical")
        critical_sec = security.lower().count("critical")
        high_sec = security.lower().count("high")
        score -= critical_bugs * 8
        score -= critical_sec * 10
        score -= high_sec * 5
        if "tech debt score" in refactor.lower():
            match = re.search(r"(\d+)\s*/\s*100", refactor)
            if match:
                debt = int(match.group(1))
                score -= debt // 5
        return max(0, min(100, score))

    def _extract_tech_debt(self, refactor: str) -> int | None:
        patterns = [
            r"tech debt score[:\s]*(\d+)",
            r"tech debt[:\s]*(\d+)\s*/\s*100",
            r"overall.*?(\d+)\s*/\s*100",
        ]
        for p in patterns:
            m = re.search(p, refactor.lower())
            if m:
                return int(m.group(1))
        warning_count = refactor.lower().count("warning")
        return min(100, 20 + warning_count * 5)

    async def _generate_changelog(self, metadata: RepoMetadata) -> str:
        return f"""# Changelog — {metadata.name}

## [Unreleased] — {datetime.utcnow().strftime('%Y-%m-%d')}

### Added
- RepoMind AI analysis completed

### Analyzed
- {metadata.file_count} source files
- {metadata.total_lines:,} lines of code
- Languages: {', '.join(metadata.languages.keys())}

### Recommended
- See Task Planner output for prioritized improvements
"""

    async def _analyze_dependencies(
        self, metadata: RepoMetadata
    ) -> list[dict[str, Any]]:
        risky_patterns = {
            "lodash": "Check for prototype pollution CVEs",
            "moment": "Consider migrating to date-fns/dayjs",
            "request": "Deprecated — use axios or fetch",
            "crypto": "Ensure not using deprecated Node crypto APIs",
            "serialize-javascript": "XSS risk in certain versions",
            "minimist": "Prototype pollution history",
            "axios": "Keep updated for SSRF fixes",
            "django": "Ensure LTS version for security patches",
            "flask": "Pin version for security updates",
        }
        risks = []
        for mgr, deps in metadata.dependencies.items():
            for dep in deps:
                dep_lower = dep.lower()
                for pattern, risk in risky_patterns.items():
                    if pattern in dep_lower:
                        risks.append({
                            "package": dep,
                            "manager": mgr,
                            "risk": risk,
                            "severity": "medium",
                        })
        return risks[:10]

    async def execute(
        self,
        result: AnalysisResult,
        metadata: RepoMetadata,
        readme: str,
        vectorstore: FaissVectorStore,
        repo_path: str,
        on_activity: ActivityCallback | None = None,
    ) -> AnalysisResult:
        snippets = vectorstore.search(
            "main entry point architecture authentication database API routes",
            top_k=8,
        )
        base_context = self._build_repo_context(metadata, readme, snippets)
        prior_outputs: dict[str, str] = {}
        agent_outputs: list[AgentOutput] = []

        for agent_name, status_msg in self.AGENT_SEQUENCE:
            event = AgentActivityEvent(
                agent=agent_name,
                status="running",
                message=status_msg,
            )
            if on_activity:
                await on_activity(event)
            result.activities.append(event)

            prompt = self._get_agent_prompt(agent_name, prior_outputs)
            accumulated_context = base_context
            if prior_outputs:
                accumulated_context += "\n\n## Previous Agent Findings\n"
                for key, val in prior_outputs.items():
                    accumulated_context += f"\n### {key}\n{val[:2000]}\n"

            try:
                content, duration_ms = await self.client.run_agent(
                    agent_name=agent_name,
                    prompt=prompt,
                    context=accumulated_context,
                    repo_path=repo_path,
                )
            except Exception as e:
                content = f"Agent {agent_name} encountered an error: {e}"

            field_map = {
                "architect": "architecture",
                "bug-hunter": "bugs",
                "security": "security",
                "refactor": "refactor",
                "documentation": "documentation",
                "task-planner": "tasks",
                "pr-review": "pr_guidelines",
            }
            workflow_key = {
                "architect": "architecture",
                "bug-hunter": "bugs",
                "security": "security",
                "refactor": "refactor",
                "documentation": "documentation",
                "task-planner": "tasks",
                "pr-review": "pr-review",
            }
            prior_outputs[workflow_key.get(agent_name, agent_name)] = content
            field = field_map.get(agent_name)
            if field:
                setattr(result, field, content)

            agent_outputs.append(AgentOutput(
                role=agent_name,
                content=content,
                duration_ms=duration_ms,
            ))

            done_event = AgentActivityEvent(
                agent=agent_name,
                status="completed",
                message=f"{agent_name.replace('-', ' ').title()} analysis complete",
                output_preview=content[:200] + "..." if len(content) > 200 else content,
            )
            if on_activity:
                await on_activity(done_event)
            result.activities.append(done_event)

        result.architecture = prior_outputs.get("architecture")
        result.bugs = prior_outputs.get("bugs")
        result.security = prior_outputs.get("security")
        result.refactor = prior_outputs.get("refactor")
        result.documentation = prior_outputs.get("documentation", getattr(result, "documentation", None))
        result.tasks = prior_outputs.get("tasks")
        result.pr_guidelines = prior_outputs.get("pr_guidelines")

        if result.architecture:
            result.mermaid_diagram = self._extract_mermaid(result.architecture)

        result.health_score = self._compute_health_score(
            result.bugs or "",
            result.security or "",
            result.refactor or "",
        )
        result.tech_debt_score = self._extract_tech_debt(result.refactor or "")
        result.changelog = await self._generate_changelog(metadata)
        result.dependency_risks = await self._analyze_dependencies(metadata)
        result.agent_outputs = agent_outputs
        result.status = AnalysisStatus.COMPLETED

        return result
