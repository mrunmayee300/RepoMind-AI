# RepoMind AI — Architecture

## Design Philosophy

RepoMind AI treats **GitAgent as the source of truth for agent behavior**. Agent identity, rules, and orchestration live in version-controlled files under `agents/` — not hardcoded in application code. The FastAPI backend is an **orchestrator**, not the agent runtime.

This mirrors how production AI platforms separate:
1. **Agent definitions** (portable, git-versioned)
2. **Orchestration logic** (workflow engine)
3. **Runtime** (GitClaw SDK or compatible fallback)

---

## Why Seven Specialist Agents?

| Agent | Rationale |
|-------|-----------|
| **Architect** | Must run first — establishes mental model for all downstream agents |
| **Bug Hunter** | Needs architecture context to prioritize likely failure points |
| **Security** | Benefits from bug patterns + architecture to scope audit |
| **Refactor** | Informed by bugs and security — avoids suggesting unsafe refactors |
| **Documentation** | Synthesizes understanding into onboarding artifacts |
| **Task Planner** | Converts findings into actionable GitHub issues |
| **PR Review** | Standalone capability for interactive PR simulation |

Single monolithic prompts produce shallow, generic output. Specialists with focused `SOUL.md` files produce deeper, structured analysis.

---

## Orchestration Logic

### Declarative Workflow (`agents/workflows/full-analysis.yaml`)

Defines:
- Agent execution order
- Per-agent prompts
- Context dependencies (`input_from`)

### Imperative Engine (`backend/app/workflows/full_analysis.py`)

```python
for agent_name, status_msg in AGENT_SEQUENCE:
    prompt = self._get_agent_prompt(agent_name, prior_outputs)
    context = base_context + prior_outputs
    content = await gitagent_client.run_agent(agent_name, prompt, context)
    prior_outputs[agent_name] = content
```

**Context passing:** Each agent receives:
1. Repository metadata (languages, frameworks, hotspots)
2. RAG-retrieved code snippets
3. README/key file content
4. Truncated outputs from prior agents in the chain

---

## GitAgent Integration

### Layer 1: Git-Native Definitions

```
agents/architect/
├── agent.yaml    # Model, tools, max_turns
├── SOUL.md       # Identity + output format
└── RULES.md      # Constraints
```

### Layer 2: Node Sidecar (`agent-runner/`)

Wraps the `gitclaw` npm package:

```typescript
const stream = query({
  dir: agentDir,
  prompt: body.prompt,
  systemPromptSuffix: body.systemPromptSuffix,
});
```

Exposes `/run` and `/run/stream` for FastAPI.

### Layer 3: Python Client (`backend/app/agents/gitagent_client.py`)

- Checks runner health at `AGENT_RUNNER_URL`
- If available → delegates to GitClaw runtime
- If unavailable → loads `SOUL.md` via `PromptLoader` and calls OpenAI

**Both paths use identical agent definitions from git.** The fallback is not a different product — it's the same agents without the GitClaw tool loop.

---

## Vector Retrieval Flow

```
1. Clone repo → parse files
2. Chunk source files (1500 chars, 200 overlap)
3. Embed via OpenAI text-embedding-3-small
4. Store in FAISS IndexFlatIP (cosine via L2 normalize)
5. On agent run: search "architecture authentication API routes"
6. Inject top-k snippets into agent context
7. On chat: same retrieval + conversational prompt
```

---

## Backend ↔ Frontend Communication

| Pattern | Use Case |
|---------|----------|
| `POST /api/analyze` | Start async analysis, return `repo_id` immediately |
| Polling `GET /api/analyze/{id}` | Dashboard polls every 3s until complete |
| SSE `GET /api/analyze/{id}/stream` | Live agent activity feed |
| `POST /api/chat` | Synchronous RAG Q&A |
| `POST /api/pr-review` | On-demand PR Review agent |

CORS configured via `CORS_ORIGINS` env var.

---

## Scalability Considerations

| Current | Production Path |
|---------|-----------------|
| In-memory analysis store | Redis / PostgreSQL |
| Local FAISS index | Pinecone / Qdrant |
| Single-worker clone | Job queue (Celery/Bull) |
| Synchronous agent chain | Parallel independent agents where possible |

---

## Security

- Secrets never committed (`.env` gitignored)
- Security agent redacts secret values in output
- GitHub token optional (public repos work without)
- Agent runner has no write access to user repos in analysis mode
