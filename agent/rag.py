"""
agent/rag.py
------------
Lightweight RAG over knowledge_base/raw_docs.

Chunking  : 500-token sliding window (word-based; no heavy tokenizer needed)
Embedding : sentence-transformers (all-MiniLM-L6-v2, ~80MB, CPU-friendly)
            Falls back to Gemini text-embedding-004 if GEMINI_API_KEY is set
            and sentence-transformers is unavailable.
Index     : FAISS flat L2 (no server, no DB, fully local)
Persistence: knowledge_base/faiss_index/ (index.faiss + metadata.json)

Public API
----------
    from agent.rag import ingest, retrieve

    ingest()                        # build / rebuild the index
    chunks = retrieve("MEL", k=3)  # returns list of {"text", "source", "score"}

Run ingest from CLI:
    python -m agent.rag
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# -- project root on sys.path -------------------------------------------------
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# -- Paths --------------------------------------------------------------------
_RAW_DOCS_DIR  = _ROOT / "knowledge_base" / "raw_docs"
_INDEX_DIR     = _ROOT / "knowledge_base" / "faiss_index"
_INDEX_FILE    = _INDEX_DIR / "index.faiss"
_META_FILE     = _INDEX_DIR / "metadata.json"

# -- Chunking constants -------------------------------------------------------
CHUNK_SIZE_TOKENS   = 500   # approximate word count per chunk
CHUNK_OVERLAP_TOKENS = 50   # overlap to preserve context across boundaries


# =============================================================================
# 1.  Chunking
# =============================================================================

def _chunk_text(text: str, source: str) -> list[dict]:
    """
    Split text into overlapping word-based chunks.

    Returns list of {"text": str, "source": str}
    """
    words  = text.split()
    chunks = []
    start  = 0

    while start < len(words):
        end       = min(start + CHUNK_SIZE_TOKENS, len(words))
        chunk_txt = " ".join(words[start:end])
        chunks.append({"text": chunk_txt, "source": source})
        if end == len(words):
            break
        start += CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS

    return chunks


def _load_raw_docs() -> list[dict]:
    """Read all .txt files in raw_docs/, return list of chunks."""
    all_chunks: list[dict] = []
    if not _RAW_DOCS_DIR.exists():
        log.warning("raw_docs directory not found: %s", _RAW_DOCS_DIR)
        return all_chunks

    for doc_path in sorted(_RAW_DOCS_DIR.glob("*.txt")):
        text = doc_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue
        chunks = _chunk_text(text, source=doc_path.name)
        all_chunks.extend(chunks)
        log.info("Loaded %s -> %d chunks", doc_path.name, len(chunks))

    return all_chunks


# =============================================================================
# 2.  Embeddings  (sentence-transformers preferred; Gemini API fallback)
# =============================================================================

def _get_embedder():
    """
    Returns a callable: texts (list[str]) -> np.ndarray (N, dim).
    Tries sentence-transformers first, then Gemini embedding API.
    """
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        log.info("Embedder: sentence-transformers/all-MiniLM-L6-v2")

        def _st_embed(texts: list[str]):
            import numpy as np
            vecs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            return vecs.astype("float32")

        return _st_embed

    except ImportError:
        pass

    # Fallback: Gemini embedding via google-generativeai
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        log.info("Embedder: Gemini text-embedding-004 (fallback)")

        def _gemini_embed(texts: list[str]):
            import numpy as np
            vecs = []
            for t in texts:
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=t,
                    task_type="retrieval_document",
                )
                vecs.append(result["embedding"])
            return np.array(vecs, dtype="float32")

        return _gemini_embed

    raise RuntimeError(
        "No embedding backend available. "
        "Install sentence-transformers OR set GEMINI_API_KEY."
    )


# =============================================================================
# 3.  Ingest  (build / rebuild FAISS index)
# =============================================================================

def ingest(force: bool = False) -> int:
    """
    Build the FAISS index from raw_docs/.

    Parameters
    ----------
    force : bool
        If False and index already exists, skip rebuild.

    Returns
    -------
    int  Number of chunks indexed.
    """
    if not force and _INDEX_FILE.exists() and _META_FILE.exists():
        log.info("FAISS index already exists. Use ingest(force=True) to rebuild.")
        return _load_metadata().__len__()

    chunks = _load_raw_docs()
    if not chunks:
        log.warning("No documents found in %s. Index not built.", _RAW_DOCS_DIR)
        return 0

    texts = [c["text"] for c in chunks]
    embed = _get_embedder()
    vectors = embed(texts)

    try:
        import faiss
    except ImportError:
        raise ImportError(
            "faiss-cpu is required. Add it to agent/requirements.txt and run:\n"
            "  pip install faiss-cpu"
        )

    dim   = vectors.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(vectors)

    _INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(_INDEX_FILE))

    meta = [{"text": c["text"], "source": c["source"]} for c in chunks]
    _META_FILE.write_text(json.dumps(meta, indent=2, ensure_ascii=False))

    log.info("FAISS index built: %d chunks, dim=%d -> %s", len(chunks), dim, _INDEX_DIR)
    return len(chunks)


def _load_metadata() -> list[dict]:
    if not _META_FILE.exists():
        return []
    return json.loads(_META_FILE.read_text())


# =============================================================================
# 4.  Retrieve
# =============================================================================

def retrieve(query: str, k: int = 3) -> list[dict]:
    """
    Search the FAISS index for the top-k chunks most relevant to query.

    Parameters
    ----------
    query : str
        Natural-language query (e.g. "MEL management bleeding rapid growth").
    k : int
        Number of results to return.

    Returns
    -------
    list of {"text": str, "source": str, "score": float}
        score is L2 distance (lower = more similar).
        Returns [] if index not found or empty.
    """
    if not _INDEX_FILE.exists():
        log.warning("FAISS index not found. Call ingest() first.")
        return []

    meta = _load_metadata()
    if not meta:
        return []

    try:
        import faiss
    except ImportError:
        log.error("faiss-cpu not installed.")
        return []

    embed  = _get_embedder()
    q_vec  = embed([query])                  # (1, dim)
    index  = faiss.read_index(str(_INDEX_FILE))

    k_clamped = min(k, len(meta))
    scores, idxs = index.search(q_vec, k_clamped)

    results = []
    for score, idx in zip(scores[0], idxs[0]):
        if idx < 0 or idx >= len(meta):
            continue
        results.append({
            "text":   meta[idx]["text"],
            "source": meta[idx]["source"],
            "score":  float(score),
        })

    return results


# =============================================================================
# 5.  CLI  — python -m agent.rag
# =============================================================================

if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Build RAG index from knowledge_base/raw_docs")
    parser.add_argument("--force", action="store_true", help="Force rebuild even if index exists")
    parser.add_argument("--query", type=str, default=None, help="Test query after ingest")
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    n = ingest(force=args.force)
    print(f"\nIndexed {n} chunks into {_INDEX_DIR}")

    if args.query:
        print(f"\nQuery: {args.query!r}")
        results = retrieve(args.query, k=args.k)
        for i, r in enumerate(results, 1):
            print(f"\n--- Result {i} (score={r['score']:.2f}) [{r['source']}] ---")
            print(r["text"][:300] + "..." if len(r["text"]) > 300 else r["text"])
