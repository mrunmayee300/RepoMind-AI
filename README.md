# RepoMind AI

**Autonomous GitHub Engineering Assistant** — powered by [GitAgent](https://github.com/open-gitagent/gitagent) (GitClaw)

[![Lyzr Builder Challenge](https://img.shields.io/badge/Lyzr-Builder%20Challenge-violet)](https://www.lyzr.ai/)
[![GitAgent](https://img.shields.io/badge/GitAgent-Orchestration-blue)](https://github.com/open-gitagent/gitagent)

> Cursor + GitHub Copilot + AI Tech Lead — in one platform.

RepoMind AI is a full-stack developer productivity platform where users connect a GitHub repository and **seven specialized AI agents** analyze architecture, find bugs, audit security, suggest refactors, generate documentation, create tasks, and review PRs — all orchestrated through GitAgent's git-native agent framework.

---

## Features

| Feature | Description |
|---------|-------------|
| **Repository Analyzer** | Clone, parse, embed, and summarize any public GitHub repo |
| **7 Specialist Agents** | Architect, Bug Hunter, Security, Refactor, Documentation, Task Planner, PR Review |
| **Multi-Agent Orchestration** | Sequential workflow with context passing between agents |
| **Live Agent Feed** | Real-time SSE stream of agent activity during analysis |
| **RAG Code Chat** | Ask your repository anything via vector search |
| **PR Review Simulator** | Paste diffs for AI-powered code review |
| **Engineering Health Score** | Composite score from bug/security/refactor analysis |
| **Dependency Risk Analyzer** | Flags risky packages from manifest files |
| **Auto Changelog** | Generated changelog from analysis metadata |
| **Architecture Diagrams** | Mermaid diagrams from Architect agent |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Next.js 15 Frontend                          │
│  Landing · Dashboard · Analysis · Chat · PR Review               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST + SSE
┌──────────────────────────▼──────────────────────────────────────┐
│                     FastAPI Backend                                │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │
│  │ Repo        │  │ FAISS Vector │  │ Full Analysis Workflow  │  │
│  │ Ingestion   │  │ Store (RAG)  │  │ (7-agent orchestration) │  │
│  └─────────────┘  └──────────────┘  └───────────┬─────────────┘  │
└─────────────────────────────────────────────────┼─────────────────┘
                                                  │
                    ┌─────────────────────────────▼─────────────────┐
                    │         GitAgent Client                        │
                    │  Primary: Node sidecar (gitclaw SDK)           │
                    │  Fallback: OpenAI + git-native SOUL.md prompts │
                    └─────────────────────────────┬─────────────────┘
                                                  │
┌─────────────────────────────────────────────────▼─────────────────┐
│  agents/  (Git-native agent definitions — GAP compatible)           │
│  orchestrator · architect · bug-hunter · security · refactor ·     │
│  documentation · task-planner · pr-review · workflows/            │
└───────────────────────────────────────────────────────────────────┘
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed design decisions.

---

## Project Structure

```
repomind-ai/
├── agents/                 # GitAgent agent definitions (SOUL.md, agent.yaml)
│   ├── orchestrator/
│   ├── architect/
│   ├── bug-hunter/
│   ├── security/
│   ├── refactor/
│   ├── documentation/
│   ├── task-planner/
│   ├── pr-review/
│   └── workflows/
│       └── full-analysis.yaml
├── agent-runner/           # Node.js GitClaw sidecar
├── backend/                # FastAPI Python API
│   ├── app/
│   │   ├── agents/         # GitAgent client + prompt loader
│   │   ├── api/            # REST routes
│   │   ├── services/       # Ingestion, parsing, chat
│   │   ├── workflows/      # Multi-agent orchestration
│   │   └── vectorstore/    # FAISS embeddings
│   └── main.py
├── frontend/               # Next.js 15 + Tailwind + shadcn/ui
├── docker-compose.yml
└── README.md
```

---

## Quick Start

### Prerequisites

- **Node.js 20+**
- **Python 3.12+** (3.14 supported with updated pydantic)
- **Git**
- **OpenAI API key** (for embeddings + agents)

### 1. Clone & Configure

```bash
git clone <your-repo-url>
cd repomind-ai
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
```

### 2. Install Dependencies

```bash
# Backend
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\pip install -r requirements.txt
# macOS/Linux:
# source .venv/bin/activate && pip install -r requirements.txt

# Frontend
cd ../frontend
npm install

# GitAgent runner (optional but recommended)
cd ../agent-runner
npm install
```

### 3. Run Services

**Terminal 1 — Backend:**
```bash
cd backend
# Windows:
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
# macOS/Linux:
# uvicorn main:app --reload --port 8000
```

**Terminal 2 — GitAgent Runner (optional):**
```bash
cd agent-runner
npm run dev
```

**Terminal 3 — Frontend:**
```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** → Dashboard → paste a GitHub URL → Analyze.

### Docker

```bash
docker compose up --build
```

---

## Agent Workflow

The `full-analysis` workflow runs agents in sequence, passing context forward:

```
Architect → Bug Hunter → Security → Refactor → Documentation → Task Planner → PR Review
```

Each agent loads its identity from git-native files:
- `agents/<name>/SOUL.md` — role and output format
- `agents/<name>/agent.yaml` — model, tools, constraints
- `agents/<name>/RULES.md` — behavioral rules

Orchestration is implemented in `backend/app/workflows/full_analysis.py` and defined declaratively in `agents/workflows/full-analysis.yaml`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check + GitAgent runner status |
| POST | `/api/analyze` | Start repository analysis |
| GET | `/api/analyze/{repo_id}` | Get analysis results |
| GET | `/api/analyze/{repo_id}/stream` | SSE agent activity stream |
| POST | `/api/chat` | RAG Q&A over repository |
| POST | `/api/pr-review` | PR review via PR Review agent |
| GET | `/api/agents` | List configured agents |

---

## Demo

See [DEMO_SCRIPT.md](./DEMO_SCRIPT.md) for a 3–5 minute recruiter walkthrough.

**Quick demo repo:** `https://github.com/tiangolo/typer` (lightweight; clones in seconds)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15, TypeScript, TailwindCSS, shadcn/ui |
| Backend | FastAPI, Python, Pydantic |
| AI Agents | GitAgent / GitClaw (git-native agents) |
| Embeddings | OpenAI text-embedding-3-small |
| Vector DB | FAISS |
| Repo Parsing | GitPython, custom AST walker |
| Orchestration | Custom workflow engine + YAML definitions |

---

## Submission

Built for the **Lyzr Builder Challenge** using [GitAgent](https://github.com/open-gitagent/gitagent).

See [SUBMISSION.md](./SUBMISSION.md) for form answers.

---

## License

MIT
