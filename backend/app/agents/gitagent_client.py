import json
import logging
import time
from typing import Any, AsyncGenerator

import httpx
from openai import AsyncOpenAI

from app.agents.prompt_loader import PromptLoader
from app.config import settings

logger = logging.getLogger(__name__)


class GitAgentClient:
    """
    Client for GitAgent/GitClaw agents.

    Default: OpenAI with git-native SOUL.md prompts (fast, reliable for demos).
    Optional: GitClaw runner when USE_GITAGENT_RUNNER=true.
    """

    def __init__(self) -> None:
        self.prompt_loader = PromptLoader()
        self.runner_url = settings.agent_runner_url.rstrip("/")
        self.openai = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def is_runner_available(self) -> bool:
        if not settings.use_gitagent_runner:
            return False
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.runner_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def run_agent(
        self,
        agent_name: str,
        prompt: str,
        context: str = "",
        repo_path: str | None = None,
    ) -> tuple[str, int]:
        """Run agent and return (content, duration_ms)."""
        start = time.time()
        context = self._truncate(context, settings.max_agent_context_chars)

        if await self.is_runner_available():
            try:
                content = await self._run_via_gitclaw(agent_name, prompt, context, repo_path)
                if content.strip():
                    return content, int((time.time() - start) * 1000)
            except Exception as e:
                logger.warning("GitClaw agent %s failed, using OpenAI: %s", agent_name, e)

        content = await self._run_via_openai(agent_name, prompt, context)
        duration_ms = int((time.time() - start) * 1000)
        return content, duration_ms

    async def run_agent_stream(
        self,
        agent_name: str,
        prompt: str,
        context: str = "",
    ) -> AsyncGenerator[dict[str, Any], None]:
        context = self._truncate(context, settings.max_agent_context_chars)
        if await self.is_runner_available():
            try:
                async for event in self._stream_via_gitclaw(agent_name, prompt, context):
                    yield event
                return
            except Exception:
                pass
        content, _ = await self._run_via_openai(agent_name, prompt, context)
        yield {"type": "delta", "content": content}
        yield {"type": "done", "content": content}

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 80] + "\n\n...[context truncated for token limits]..."

    async def _run_via_gitclaw(
        self,
        agent_name: str,
        prompt: str,
        context: str,
        repo_path: str | None,
    ) -> str:
        agent_dir = str(settings.agents_path / agent_name)
        payload = {
            "dir": agent_dir,
            "prompt": prompt,
            "systemPromptSuffix": context,
            "maxTurns": 8,
        }
        if repo_path:
            payload["repoPath"] = repo_path

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(f"{self.runner_url}/run", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("content", "")

    async def _stream_via_gitclaw(
        self,
        agent_name: str,
        prompt: str,
        context: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        agent_dir = str(settings.agents_path / agent_name)
        payload = {
            "dir": agent_dir,
            "prompt": prompt,
            "systemPromptSuffix": context,
            "maxTurns": 8,
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream(
                "POST",
                f"{self.runner_url}/run/stream",
                json=payload,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            yield json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

    async def _run_via_openai(
        self,
        agent_name: str,
        prompt: str,
        context: str,
    ) -> str:
        if not self.openai:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to .env in the project root."
            )

        system_prompt = self.prompt_loader.load_agent_prompt(agent_name)
        model = self.prompt_loader.get_agent_model(agent_name)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        if context:
            messages.append({
                "role": "user",
                "content": f"## Repository Context\n\n{context}",
            })
        messages.append({"role": "user", "content": prompt})

        response = await self.openai.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""
