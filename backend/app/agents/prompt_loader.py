from pathlib import Path

import yaml

from app.config import settings


class PromptLoader:
    """Load GitAgent agent definitions from git-native agent repos."""

    def __init__(self, agents_root: Path | None = None) -> None:
        self.agents_root = agents_root or settings.agents_path

    def load_agent_prompt(self, agent_name: str) -> str:
        agent_dir = self.agents_root / agent_name
        parts: list[str] = []

        soul = agent_dir / "SOUL.md"
        if soul.exists():
            parts.append(soul.read_text(encoding="utf-8"))

        rules = agent_dir / "RULES.md"
        if rules.exists():
            parts.append(f"\n## Rules\n{rules.read_text(encoding='utf-8')}")

        duties = agent_dir / "DUTIES.md"
        if duties.exists():
            parts.append(f"\n## Duties\n{duties.read_text(encoding='utf-8')}")

        return "\n".join(parts) if parts else f"You are the {agent_name} agent."

    def load_workflow(self, workflow_name: str) -> dict:
        workflow_path = self.agents_root / "workflows" / f"{workflow_name}.yaml"
        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow not found: {workflow_path}")
        with open(workflow_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_agent_model(self, agent_name: str) -> str:
        agent_yaml = self.agents_root / agent_name / "agent.yaml"
        if agent_yaml.exists():
            with open(agent_yaml, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            model_cfg = data.get("model", {})
            preferred = model_cfg.get("preferred", "")
            if preferred.startswith("openai:"):
                return preferred.split(":", 1)[1]
            if preferred:
                return preferred
        return settings.chat_model

    def list_agents(self) -> list[str]:
        agents = []
        if not self.agents_root.exists():
            return agents
        for item in self.agents_root.iterdir():
            if item.is_dir() and (item / "agent.yaml").exists():
                agents.append(item.name)
        return agents
