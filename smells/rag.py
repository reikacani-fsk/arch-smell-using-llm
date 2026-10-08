"""C4 context: retrieval over (a) the project's classes in neighbouring packages and
(b) a small knowledge base of smell/refactoring notes (markdown files in knowledge/).

NEVER put Designite/tool output or benchmark labels into this index.
"""
import hashlib
from pathlib import Path

import numpy as np

from .code_context import skeleton

CHUNK_CHARS = 3000


class HashEmbedder:
    """Offline bag-of-tokens embedder for tests (no model download). Not for real experiments."""
    dim = 256

    def encode(self, texts):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in t.replace(".", " ").replace("(", " ").split():
                out[i, int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


def make_embedder(name: str):
    if name == "hash":
        return HashEmbedder()
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name, trust_remote_code=True)


def _embed(embedder, texts):
    return np.asarray(embedder.encode(texts)).tolist()


def build_index(index: dict, knowledge_dir: Path, db_dir: Path, embedder_name: str):
    import chromadb
    client = chromadb.PersistentClient(path=str(db_dir))
    for name in ("code", "knowledge"):
        try:
            client.delete_collection(name)
        except Exception:
            pass
    emb = make_embedder(embedder_name)
    code = client.create_collection("code", metadata={"hnsw:space": "cosine"})
    ids, docs, metas = [], [], []
    for pkg, files in index.items():
        for f in files:
            doc = f"// {pkg}.{f.path.stem}\n" + skeleton(f.text, f.language)[:CHUNK_CHARS]
            uid = f"{pkg}.{f.path.stem}"              # C# may repeat a file name within a namespace
            ids.append(uid if uid not in ids else f"{uid}#{len(ids)}")
            docs.append(doc)
            metas.append({"package": pkg})
    for i in range(0, len(docs), 64):
        code.add(ids=ids[i:i + 64], documents=docs[i:i + 64], metadatas=metas[i:i + 64],
                 embeddings=_embed(emb, docs[i:i + 64]))
    kb = client.create_collection("knowledge", metadata={"hnsw:space": "cosine"})
    notes = sorted(Path(knowledge_dir).glob("*.md")) if Path(knowledge_dir).exists() else []
    chunks = []
    for n in notes:
        for j, part in enumerate(n.read_text(encoding="utf-8").split("\n## ")):
            if part.strip():
                chunks.append((f"{n.stem}-{j}", part.strip()))
    if chunks:
        kb.add(ids=[c[0] for c in chunks], documents=[c[1] for c in chunks],
               embeddings=_embed(emb, [c[1] for c in chunks]))
    return len(docs), len(chunks)


class Retriever:
    def __init__(self, db_dir: Path, embedder_name: str):
        import chromadb
        self.client = chromadb.PersistentClient(path=str(db_dir))
        self.code = self.client.get_collection("code")
        self.kb = self.client.get_collection("knowledge")
        self.emb = make_embedder(embedder_name)

    def context(self, package: str, query_text: str, neighbours: list[str], k: int) -> str:
        q = _embed(self.emb, [query_text[:CHUNK_CHARS]])
        parts = [f"[Retrieved context for {package}]"]
        if neighbours:
            r = self.code.query(query_embeddings=q, n_results=k,
                                where={"package": {"$in": neighbours}} if len(neighbours) > 1
                                else {"package": neighbours[0]})
            for doc in r["documents"][0]:
                parts.append("Related class from a neighbouring package:\n" + doc)
        if self.kb.count():
            r = self.kb.query(query_embeddings=q, n_results=min(k, self.kb.count()))
            for doc in r["documents"][0]:
                parts.append("Architecture knowledge note:\n" + doc)
        return "\n\n".join(parts)
