from backend.config import settings
from backend.llm_client import get_llm_client
from backend.vectorstore import query as vector_query

SYSTEM_PROMPT = """You are a project operations assistant. Answer the user's question
using ONLY the numbered source excerpts provided. Reference sources inline like [1], [2].
If the excerpts don't contain the answer, say so plainly instead of guessing."""


def answer_question(project: str, question: str, top_k: int | None = None) -> dict:
    top_k = top_k or settings.TOP_K
    hits = vector_query(project=project, question=question, top_k=top_k)

    if not hits:
        return {
            "answer": f"I couldn't find any indexed documents for project '{project}' yet. "
                      f"Upload some documents first.",
            "sources": [],
        }

    context_blocks = []
    for i, hit in enumerate(hits, start=1):
        context_blocks.append(f"[{i}] (from {hit['filename']}): {hit['text']}")
    context = "\n\n".join(context_blocks)

    user_prompt = f"""Question: {question}

Sources:
{context}

Answer the question using only the sources above, citing them as [1], [2], etc."""

    llm = get_llm_client()
    answer = llm.generate(SYSTEM_PROMPT, user_prompt)

    sources = [{"document": hit["filename"], "snippet": hit["text"][:300]} for hit in hits]
    return {"answer": answer, "sources": sources}
