"""Thin wrapper around ChromaDB.

Uses Chroma's bundled default embedding function (ONNX MiniLM) so no GPU,
torch, or paid embedding API is required — everything runs locally and free.
"""
import chromadb
from chromadb.utils import embedding_functions

from backend.config import settings

_client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
_embedder = embedding_functions.DefaultEmbeddingFunction()

_collection = _client.get_or_create_collection(
    name="project_docs",
    embedding_function=_embedder,
)


def add_chunks(document_id: int, project: str, filename: str, chunks: list[str]) -> int:
    if not chunks:
        return 0
    ids = [f"doc{document_id}_chunk{i}" for i in range(len(chunks))]
    metadatas = [
        {"document_id": document_id, "project": project, "filename": filename, "chunk_index": i}
        for i in range(len(chunks))
    ]
    _collection.add(ids=ids, documents=chunks, metadatas=metadatas)
    return len(chunks)


def query(project: str, question: str, top_k: int = 5) -> list[dict]:
    results = _collection.query(
        query_texts=[question],
        n_results=top_k,
        where={"project": project},
    )
    hits = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    for text, meta in zip(docs, metas):
        hits.append({"text": text, "filename": meta.get("filename"), "document_id": meta.get("document_id")})
    return hits


def delete_document(document_id: int) -> None:
    _collection.delete(where={"document_id": document_id})


def delete_project(project: str) -> None:
    _collection.delete(where={"project": project})
