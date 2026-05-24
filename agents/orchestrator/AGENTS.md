# Agent Delegation Rules

## Specialist Agents

| Agent | Directory | When to Use |
|-------|-----------|-------------|
| Architect | `../architect` | System design, architecture maps, module boundaries |
| Bug Hunter | `../bug-hunter` | Suspicious patterns, logic bugs, error handling gaps |
| Refactor | `../refactor` | Code structure improvements, tech debt |
| Documentation | `../documentation` | README, onboarding guides, API docs |
| Task Planner | `../task-planner` | GitHub issues, sprint tasks, actionable items |
| Security | `../security` | Secrets, auth weaknesses, OWASP risks |
| PR Review | `../pr-review` | Pull request reviews, diff analysis |

## Workflow Order (Full Analysis)

1. **Architect** — Understand system design first
2. **Bug Hunter** — Scan for issues with architecture context
3. **Security** — Audit with architecture + bug context
4. **Refactor** — Suggest improvements informed by above
5. **Documentation** — Generate docs from full context
6. **Task Planner** — Create actionable tasks from all findings

## Context Passing

Each agent receives:
- Repository metadata (languages, frameworks, structure)
- Code snippets from vector retrieval
- Prior agent outputs as `context` in the prompt
