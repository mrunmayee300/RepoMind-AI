from openai import AsyncOpenAI

from app.agents.prompt_loader import PromptLoader
from app.config import settings
from app.vectorstore.faiss_store import FaissVectorStore


class ChatService:
    """RAG-powered repository Q&A."""

    def __init__(self) -> None:
        self.prompt_loader = PromptLoader()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def ask(self, repo_id: str, question: str, top_k: int = 5) -> dict:
        store = FaissVectorStore(repo_id)
        snippets = store.search(question, top_k=top_k)

        context = ""
        sources = []
        for snip in snippets:
            context += f"\n### {snip['file']}\n```\n{snip['content']}\n```\n"
            sources.append({"file": snip["file"], "score": snip["score"]})

        if not self.client:
            return {
                "answer": "OPENAI_API_KEY required for chat.",
                "sources": sources,
            }

        system = """You are RepoMind AI, an expert on the connected GitHub repository.
Answer questions using ONLY the provided code context. Cite file paths.
If unsure, say so. Be concise and technical."""

        response = await self.client.chat.completions.create(
            model=settings.chat_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
            ],
            temperature=0.2,
            max_tokens=2048,
        )

        return {
            "answer": response.choices[0].message.content or "",
            "sources": sources,
        }
